"""Sync pipeline: pull recent Form 470s from USAC, filter to Mission
Telecom-relevant services, aggregate service-request rows into one RFP per
application, download attached documents, estimate prior spend, and score.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from . import config, db, docs, scoring, soda, spend, status as status_mod

log = logging.getLogger(__name__)

# service_type values in the 470 dataset that Mission Telecom can bid on.
RELEVANT_SERVICE_TYPES = {
    "data transmission and/or internet access",
    "internal connections",
    "managed internal broadband services",
    "basic maintenance of internal connections",
    "voice",  # kept out below — placeholder to show intent; voice is excluded
}
EXCLUDED_SERVICE_TYPES = {"voice"}

# Functions that indicate connectivity/wireless work (used for relevance and
# scoring). Anything matching a relevant service_type passes; functions refine.
CONNECTIVITY_FUNCTIONS = [
    "internet access", "data transmission", "leased lit fiber",
    "leased dark fiber", "wireless", "cellular", "broadband",
    "network equipment", "maintenance and operations",
    "access points", "controllers", "switches", "routers", "firewall",
    "cabling", "antennas", "racks", "ups", "battery", "caching", "equipment",
]


def is_relevant(service_type: str | None, function: str | None) -> bool:
    st = (service_type or "").strip().lower()
    if st in EXCLUDED_SERVICE_TYPES:
        return False
    return st in RELEVANT_SERVICE_TYPES


def run_sync(lookback_days: int | None = None, download_docs: bool = True,
             max_doc_downloads: int = 200) -> dict:
    """Full sync. Returns a summary dict; also recorded in sync_log."""
    started = datetime.now(timezone.utc)
    summary = {"pulled_rows": 0, "applications": 0, "relevant": 0,
               "docs_downloaded": 0, "errors": []}
    with db.closing_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sync_log (started_at, status) VALUES (?, 'RUNNING')",
            (started.isoformat(),))
        sync_id = cur.lastrowid
        conn.commit()

    try:
        rows = _pull_recent_470s(lookback_days)
        summary["pulled_rows"] = len(rows)
        apps = _aggregate(rows)
        summary["applications"] = len(apps)
        _upsert(apps)
        summary["relevant"] = sum(1 for a in apps.values() if a["relevant"])
        _update_prior_spend()
        if download_docs:
            summary["docs_downloaded"] = _download_open_docs(max_doc_downloads)
        scoring.score_all()
        _finish(sync_id, "OK", summary)
    except Exception as e:
        log.exception("sync failed")
        summary["errors"].append(str(e))
        _finish(sync_id, "ERROR", summary)
        raise
    return summary


def _finish(sync_id: int, status: str, summary: dict) -> None:
    with db.closing_conn() as conn:
        conn.execute(
            "UPDATE sync_log SET finished_at=?, status=?, detail=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), status,
             json.dumps(summary), sync_id))
        conn.commit()


def _pull_recent_470s(lookback_days: int | None = None) -> list:
    lookback = lookback_days or config.SYNC_LOOKBACK_DAYS
    since = (datetime.now(timezone.utc) - timedelta(days=lookback))
    where = (f"certified_date_time > '{since.strftime('%Y-%m-%dT00:00:00')}' "
             "AND fcc_form_470_status = 'Certified'")
    return soda.fetch_all(config.DATASET_FORM470, where=where,
                          order="application_number")


def _aggregate(rows: list) -> dict:
    """Collapse per-service-request rows into one record per application."""
    apps: dict[str, dict] = {}
    for r in rows:
        an = r.get("application_number")
        if not an:
            continue
        # Prefer the 'Current' form_version rows when both exist.
        app = apps.setdefault(an, {
            "application_number": an,
            "service_requests": [],
            "service_types": set(),
            "functions": set(),
            "rfp_doc_urls": set(),
            "relevant": False,
            "form_version": r.get("form_version"),
        })
        for field, key in [
            ("form_nickname", "form_nickname"),
            ("funding_year", "funding_year"),
            ("billed_entity_number", "billed_entity_number"),
            ("billed_entity_name", "billed_entity_name"),
            ("applicant_type", "applicant_type"),
            ("billed_entity_state", "state"),
            ("billed_entity_city", "city"),
            ("billed_entity_zip", "zip"),
            ("contact_name", "contact_name"),
            ("contact_email", "contact_email"),
            ("contact_phone", "contact_phone"),
            ("website_url", "website_url"),
            ("certified_date_time", "certified_date"),
            ("allowable_contract_date", "allowable_contract_date"),
            ("category_one_description", "cat1_description"),
            ("category_two_description", "cat2_description"),
        ]:
            if r.get(field):
                app[key] = r[field]
        addr_bits = [r.get("contact_address1"), r.get("contact_address2"),
                     r.get("contact_city"), r.get("contact_state"),
                     r.get("contact_zip")]
        addr = ", ".join(b for b in addr_bits if b)
        if addr:
            app["contact_address"] = addr
        if r.get("state_or_local_restrictions") in (True, "1", "Yes"):
            app["state_or_local_restrictions"] = 1
        pdf = (r.get("form_pdf") or {}).get("url")
        if pdf:
            app["form_pdf_url"] = pdf
        rfp = (r.get("rfp_documents") or {}).get("url")
        if rfp:
            app["rfp_doc_urls"].add(rfp)
        st, fn = r.get("service_type"), r.get("function")
        if st:
            app["service_types"].add(st)
        if fn:
            app["functions"].add(fn)
        if is_relevant(st, fn):
            app["relevant"] = True
        app["service_requests"].append({
            "service_request_id": r.get("service_request_id") or "",
            "service_category": r.get("service_category"),
            "service_type": st, "function": fn,
            "quantity": r.get("quantity"), "unit": r.get("unit"),
            "min_capacity": r.get("minimum_capacity"),
            "max_capacity": r.get("maximum_capacity"),
            "entities": r.get("entities"),
            "manufacturer": r.get("manufacturer"),
        })
    return apps


def _upsert(apps: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with db.closing_conn() as conn:
        for an, a in apps.items():
            conn.execute(
                """INSERT INTO rfps (application_number, form_nickname,
                    funding_year, billed_entity_number, billed_entity_name,
                    applicant_type, state, city, zip, contact_name,
                    contact_email, contact_phone, contact_address, website_url,
                    certified_date, allowable_contract_date, form_pdf_url,
                    rfp_doc_urls, has_rfp_docs, service_types, functions,
                    cat1_description, cat2_description,
                    state_or_local_restrictions, relevant, last_synced)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(application_number) DO UPDATE SET
                    form_nickname=excluded.form_nickname,
                    allowable_contract_date=excluded.allowable_contract_date,
                    rfp_doc_urls=excluded.rfp_doc_urls,
                    has_rfp_docs=excluded.has_rfp_docs,
                    service_types=excluded.service_types,
                    functions=excluded.functions,
                    cat1_description=excluded.cat1_description,
                    cat2_description=excluded.cat2_description,
                    relevant=excluded.relevant,
                    last_synced=excluded.last_synced""",
                (an, a.get("form_nickname"), a.get("funding_year"),
                 a.get("billed_entity_number"), a.get("billed_entity_name"),
                 a.get("applicant_type"), a.get("state"), a.get("city"),
                 a.get("zip"), a.get("contact_name"), a.get("contact_email"),
                 a.get("contact_phone"), a.get("contact_address"),
                 a.get("website_url"), a.get("certified_date"),
                 a.get("allowable_contract_date"), a.get("form_pdf_url"),
                 json.dumps(sorted(a["rfp_doc_urls"])),
                 1 if a["rfp_doc_urls"] else 0,
                 json.dumps(sorted(a["service_types"])),
                 json.dumps(sorted(a["functions"])),
                 a.get("cat1_description"), a.get("cat2_description"),
                 a.get("state_or_local_restrictions", 0),
                 1 if a["relevant"] else 0, now))
            conn.execute(
                "DELETE FROM service_requests WHERE application_number=?", (an,))
            for sr in a["service_requests"]:
                conn.execute(
                    """INSERT OR IGNORE INTO service_requests
                       (application_number, service_request_id, service_category,
                        service_type, function, quantity, unit, min_capacity,
                        max_capacity, entities, manufacturer)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (an, sr["service_request_id"], sr["service_category"],
                     sr["service_type"], sr["function"], sr["quantity"],
                     sr["unit"], sr["min_capacity"], sr["max_capacity"],
                     sr["entities"], sr["manufacturer"]))
        conn.commit()


def _update_prior_spend() -> None:
    """Fill est_prior_spend for relevant RFPs missing it."""
    with db.closing_conn() as conn:
        rows = conn.execute(
            "SELECT application_number, billed_entity_number, funding_year "
            "FROM rfps WHERE relevant=1 AND est_prior_spend IS NULL").fetchall()
    if not rows:
        return
    by_fy: dict[int, list] = {}
    for r in rows:
        try:
            fy = int(r["funding_year"])
        except (TypeError, ValueError):
            continue
        by_fy.setdefault(fy, []).append(r)
    for fy, group in by_fy.items():
        bens = [r["billed_entity_number"] for r in group]
        spends = spend.prior_spend_by_ben(bens, current_fy=fy)
        with db.closing_conn() as conn:
            for r in group:
                info = spends.get(r["billed_entity_number"])
                if info:
                    conn.execute(
                        "UPDATE rfps SET est_prior_spend=? "
                        "WHERE application_number=?",
                        (info["spend"], r["application_number"]))
            conn.commit()


def _download_open_docs(cap: int) -> int:
    """Download attached RFP docs + the 470 PDF for OPEN relevant items,
    extract text, store it."""
    with db.closing_conn() as conn:
        rows = conn.execute(
            "SELECT application_number, certified_date, "
            "allowable_contract_date, form_pdf_url, rfp_doc_urls, doc_text "
            "FROM rfps WHERE relevant=1").fetchall()
    downloaded = 0
    for r in rows:
        if downloaded >= cap:
            break
        st, _ = status_mod.compute_status(
            status_mod.parse_usac_date(r["certified_date"]),
            status_mod.parse_usac_date(r["allowable_contract_date"]))
        if st == status_mod.CLOSED:
            continue
        if r["doc_text"]:  # already processed
            continue
        urls = json.loads(r["rfp_doc_urls"] or "[]")
        if r["form_pdf_url"]:
            urls = [r["form_pdf_url"]] + urls
        if not urls:
            continue
        paths = docs.download_documents(r["application_number"], urls)
        text = "\n\n---DOCUMENT BREAK---\n\n".join(
            t for t in (docs.extract_text(p) for p in paths) if t)
        with db.closing_conn() as conn:
            conn.execute(
                "UPDATE rfps SET doc_text=?, doc_files=? "
                "WHERE application_number=?",
                (text[:docs.MAX_TEXT_CHARS],
                 json.dumps([str(p.name) for p in paths]),
                 r["application_number"]))
            conn.commit()
        downloaded += 1
    return downloaded
