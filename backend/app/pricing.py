"""Price list ingestion (CSV/XLSX) and requested-service -> SKU matching.

Matching is deterministic and conservative: an RFP line item either matches a
price-list row (with a confidence tier) or is flagged unmatched for human
pricing. Prices are NEVER invented — see match_services().
"""
import csv
import io
import json
import re

from . import db

# canonical field -> header aliases (lowercased, stripped)
HEADER_ALIASES = {
    "sku": ["sku", "item", "item #", "item number", "part", "part number",
            "product code", "code", "id"],
    "description": ["description", "desc", "product", "product name",
                    "service", "service name", "item description", "name"],
    "category": ["category", "service category", "type", "service type",
                 "family", "group"],
    "unit": ["unit", "uom", "unit of measure", "per"],
    "unit_price": ["unit price", "price", "monthly price", "mrc",
                   "monthly recurring", "cost", "rate", "unit cost",
                   "price per unit"],
    "term_months": ["term", "term months", "term (months)", "contract term",
                    "months", "term_months"],
}

REQUIRED_FIELDS = ["description", "unit_price"]


def sniff_headers(headers: list[str]) -> tuple[dict, list]:
    """Map canonical field -> column index. Returns (mapping, unmapped
    required fields). Used to drive the mapping UI when headers don't match."""
    norm = [h.strip().lower() for h in headers]
    mapping = {}
    for field, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                mapping[field] = norm.index(alias)
                break
    missing = [f for f in REQUIRED_FIELDS if f not in mapping]
    return mapping, missing


def parse_rows(filename: str, content: bytes) -> tuple[list[str], list[list]]:
    """Returns (headers, data_rows) from CSV or XLSX bytes."""
    if filename.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True,
                                    data_only=True)
        ws = wb.active
        rows = [[("" if c is None else str(c)) for c in row]
                for row in ws.iter_rows(values_only=True)]
    else:
        text = content.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def import_price_list(filename: str, content: bytes,
                      mapping: dict | None = None) -> dict:
    """Validate and store the price list. If mapping is None it is sniffed;
    when required fields can't be sniffed, returns needs_mapping with the
    headers so the UI can show a column-mapping form."""
    headers, data = parse_rows(filename, content)
    if not data:
        return {"ok": False, "error": "no data rows found"}
    if mapping is None:
        mapping, missing = sniff_headers(headers)
        if missing:
            return {"ok": False, "needs_mapping": True, "headers": headers,
                    "sniffed": mapping, "missing": missing,
                    "sample_rows": data[:5]}
    items, errors = [], []
    for i, row in enumerate(data, start=2):
        def cell(field):
            idx = mapping.get(field)
            return row[idx].strip() if idx is not None and idx < len(row) else ""
        price_raw = cell("unit_price")
        price = _parse_price(price_raw)
        if price is None:
            errors.append(f"row {i}: bad price {price_raw!r}")
            continue
        if not cell("description"):
            errors.append(f"row {i}: missing description")
            continue
        term = None
        m = re.search(r"\d+", cell("term_months"))
        if m:
            term = int(m.group())
        items.append({
            "sku": cell("sku"), "description": cell("description"),
            "category": cell("category"), "unit": cell("unit"),
            "unit_price": price, "term_months": term,
            "raw": json.dumps(dict(zip(headers, row))),
        })
    if not items:
        return {"ok": False, "error": "no valid rows", "row_errors": errors}
    with db.closing_conn() as conn:
        conn.execute("DELETE FROM price_items")
        conn.executemany(
            "INSERT INTO price_items (sku, description, category, unit, "
            "unit_price, term_months, raw) VALUES "
            "(:sku, :description, :category, :unit, :unit_price, "
            ":term_months, :raw)", items)
        conn.commit()
    return {"ok": True, "imported": len(items), "row_errors": errors}


def _parse_price(raw: str):
    cleaned = re.sub(r"[$,\s]", "", raw or "")
    if not cleaned:
        return None
    try:
        v = float(cleaned)
        return v if v >= 0 else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Matching requested services to the price list
# ---------------------------------------------------------------------------

STOPWORDS = {"and", "or", "the", "of", "for", "a", "an", "to", "with",
             "necessary", "software", "licenses", "service", "services",
             "components", "related"}

SYNONYMS = {
    "wi-fi": "wireless", "wifi": "wireless", "ap": "access",
    "aps": "access", "internet": "internet", "isp": "internet",
    "wan": "data", "lan": "network", "firewalls": "firewall",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9.-]+", (text or "").lower())
    out = set()
    for w in words:
        if w in STOPWORDS or len(w) < 2:
            continue
        w = SYNONYMS.get(w, w)
        # plural fold, applied to both request and catalog sides
        if len(w) > 4 and w.endswith("es") and not w.endswith("ses"):
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def _bandwidth_mbps(text: str):
    """Pull a bandwidth figure (Mbps) out of free text like '1 Gbps',
    '1024.00 Mbps', '10G'."""
    if not text:
        return None
    m = re.search(r"([\d.]+)\s*(g|gb|gig|gbps|m|mb|mbps)", text.lower())
    if not m:
        return None
    val = float(m.group(1))
    return val * 1000 if m.group(2).startswith("g") else val


def match_services(service_requests: list[dict]) -> list[dict]:
    """For each requested service, find the best price-list row.

    GUARDRAIL: any request without a confident match gets matched=False and
    unit_price=None — the response document renders it as a red
    [NEEDS INPUT] line. We never fill a number the price list doesn't contain.
    """
    with db.closing_conn() as conn:
        catalog = [dict(r) for r in conn.execute(
            "SELECT * FROM price_items").fetchall()]
    results = []
    for sr in service_requests:
        # Match on the specific function text only — the broad service_type
        # words ("Internal Connections") must not be enough to pull a price,
        # or unrelated hardware would get priced. Manufacturer text is a
        # bonus signal, not part of the base overlap (it's often noise like
        # "Cisco or equivalent").
        req_tokens = _tokens(str(sr.get("function") or ""))
        mfr_tokens = _tokens(str(sr.get("manufacturer") or ""))
        req_bw = (_bandwidth_mbps(sr.get("max_capacity") or "")
                  or _bandwidth_mbps(sr.get("min_capacity") or ""))
        is_maintenance = "maintenance" in (sr.get("service_type") or "").lower()
        best, best_score = None, 0.0
        for item in catalog:
            item_tokens = _tokens(
                f"{item['description']} {item['category']} {item['sku']}")
            if not item_tokens or not req_tokens:
                continue
            # a maintenance request must never price a hardware SKU
            if is_maintenance and "maintenance" not in item_tokens:
                continue
            overlap = len(req_tokens & item_tokens)
            score = overlap / max(len(req_tokens), 1)
            if mfr_tokens & item_tokens:
                score += 0.2
            item_bw = _bandwidth_mbps(item["description"])
            if req_bw and item_bw:
                if abs(item_bw - req_bw) / req_bw < 0.15:
                    score += 0.5  # bandwidth agreement is a strong signal
                elif item_bw < req_bw * 0.5 or item_bw > req_bw * 4:
                    score -= 0.3
            if score > best_score:
                best, best_score = item, score
        qty = _parse_qty(sr.get("quantity"))
        if best is not None and best_score >= 0.34:
            results.append({
                "request": sr, "matched": True,
                "confidence": ("high" if best_score >= 0.6 else "medium"),
                "sku": best["sku"], "description": best["description"],
                "unit": best["unit"], "unit_price": best["unit_price"],
                "term_months": best["term_months"], "quantity": qty,
                "extended_price": (round(best["unit_price"] * qty, 2)
                                   if qty else None),
            })
        else:
            results.append({"request": sr, "matched": False,
                            "confidence": None, "sku": None,
                            "description": None, "unit": None,
                            "unit_price": None, "term_months": None,
                            "quantity": qty, "extended_price": None})
    return results


def _parse_qty(raw):
    try:
        q = float(str(raw))
        return int(q) if q == int(q) else q
    except (TypeError, ValueError):
        return None
