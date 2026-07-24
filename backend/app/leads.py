"""Lead generation from public data: which districts already buy LTE, from
whom, for how much, when the contract expires, and who to talk to.

Sources (all public):
- USAC Form 471 FRN Status (DATASET_FRN_STATUS): actual funded spend per
  district per year, the incumbent provider (spin_name), the filing contact
  email (cnct_email), the E-Rate consultant (crn_data), the narrative, and
  the contract expiration date.
- Urban Institute Education Data API (NCES CCD, free, no key): district
  enrollment and total budget (best-effort enrichment; skipped on failure).

The killer query: districts whose 471 lines are billed by a cellular carrier
(T-Mobile, Verizon, AT&T Mobility, Kajeet...) or whose narratives say
LTE/hotspot/cellular — proven LTE budget, a named incumbent to displace, and
a date when the contract is up.
"""
import datetime
import hashlib
import json
import logging
import re
import time

import httpx

from . import config, db, soda

log = logging.getLogger(__name__)

# spin_name substrings that mean the incumbent bills cellular/LTE service
CELLULAR_CARRIERS = (
    "t-mobile", "tmobile", "verizon", "cellco", "at&t mobility",
    "att mobility", "at&t mobil", "sprint", "kajeet", "mobile citizen",
    "mobile beacon", "us cellular", "u.s. cellular", "cricket",
    "dish wireless", "boost mobile", "firstnet",
)
# narrative/nickname terms that mean the service itself is LTE/wireless WAN.
# Word-boundary matched: "5Gbps fiber" must NOT match "5g", and words like
# "complete" must not match "lte".
_LTE_NARRATIVE_RE = re.compile(
    r"\b(lte|hotspots?|hot ?spots?|cellular|4g|5g|wireless wan|"
    r"mobile broadband|mobile data|mifi|jetpacks?|cradlepoint|"
    r"fixed wireless|wireless internet)\b")

URBAN_BASE = "https://educationdata.urban.org/api/v1/school-districts/ccd"
DIRECTORY_YEAR = 2022   # latest CCD directory vintage on the API
FINANCE_YEAR = 2020     # latest CCD finance vintage on the API
ENRICH_TTL = 7 * 24 * 3600

STATE_FIPS = {
    "AL": 1, "AK": 2, "AZ": 4, "AR": 5, "CA": 6, "CO": 8, "CT": 9, "DE": 10,
    "DC": 11, "FL": 12, "GA": 13, "HI": 15, "ID": 16, "IL": 17, "IN": 18,
    "IA": 19, "KS": 20, "KY": 21, "LA": 22, "ME": 23, "MD": 24, "MA": 25,
    "MI": 26, "MN": 27, "MS": 28, "MO": 29, "MT": 30, "NE": 31, "NV": 32,
    "NH": 33, "NJ": 34, "NM": 35, "NY": 36, "NC": 37, "ND": 38, "OH": 39,
    "OK": 40, "OR": 41, "PA": 42, "RI": 44, "SC": 45, "SD": 46, "TN": 47,
    "TX": 48, "UT": 49, "VT": 50, "VA": 51, "WA": 53, "WV": 54, "WI": 55,
    "WY": 56,
}


def current_funding_year() -> int:
    """E-Rate funding year N runs July N through June N+1."""
    today = datetime.date.today()
    return today.year if today.month >= 7 else today.year - 1


def find_leads(state: str, name_contains: list[str] | None = None,
               wireless_only: bool = True, limit: int = 12,
               enrich: bool = True) -> dict:
    """Find districts in `state` with funded internet/data 471 lines.

    name_contains: optional city/district keywords for metro targeting
    (e.g. DFW -> ["Dallas", "Fort Worth", "Arlington", "Plano", ...]).
    wireless_only: keep only leads with an LTE/cellular signal (carrier
    incumbent or LTE narrative). False = all connectivity buyers.
    """
    state = (state or "").strip().upper()
    fy = current_funding_year()
    # A funding year starts in July and fills in over months — use whichever
    # of the current/prior year has the richer picture of who buys what.
    cur_rows = _frn_rows(state, fy)
    prev_rows = _frn_rows(state, fy - 1)
    if len(prev_rows) > len(cur_rows):
        used_fy, rows = fy - 1, prev_rows
    else:
        used_fy, rows = fy, cur_rows

    # aggregate by billed entity
    orgs: dict[str, dict] = {}
    for r in rows:
        ben = r.get("ben") or ""
        if not ben:
            continue
        o = orgs.setdefault(ben, {
            "ben": ben,
            "name": r.get("organization_name") or "",
            "entity_type": r.get("organization_entity_type_name") or "",
            "total_spend": 0.0, "wireless_spend": 0.0,
            "providers": set(), "wireless_providers": set(),
            "contacts": set(), "consultants": set(),
            "narratives": [], "expirations": [],
        })
        spend = _f(r.get("total_pre_discount_costs"))
        o["total_spend"] += spend
        spin = (r.get("spin_name") or "").strip()
        if spin:
            o["providers"].add(spin)
        if r.get("cnct_email"):
            o["contacts"].add(r["cnct_email"].strip().lower())
        cons = _consultant(r.get("crn_data"))
        if cons:
            o["consultants"].add(cons)
        text = f"{r.get('narrative') or ''} {r.get('nickname') or ''}".lower()
        is_wireless = (any(c in spin.lower() for c in CELLULAR_CARRIERS)
                       or bool(_LTE_NARRATIVE_RE.search(text)))
        if is_wireless:
            o["wireless_spend"] += spend
            if spin:
                o["wireless_providers"].add(spin)
            exp = (r.get("contract_expiration_date") or "")[:10]
            if exp:
                o["expirations"].append(exp)
            nar = (r.get("narrative") or r.get("nickname") or "").strip()
            if nar and len(o["narratives"]) < 3:
                o["narratives"].append(nar[:140])

    leads = list(orgs.values())
    if name_contains:
        pats = [p.strip().lower() for p in name_contains if p and p.strip()]
        if pats:
            leads = [o for o in leads
                     if any(p in o["name"].lower() for p in pats)]
    if wireless_only:
        leads = [o for o in leads if o["wireless_spend"] > 0]
    leads.sort(key=lambda o: (o["wireless_spend"], o["total_spend"]),
               reverse=True)
    leads = leads[:max(1, min(int(limit or 12), 40))]

    for o in leads:
        o["providers"] = sorted(o["providers"])
        o["wireless_providers"] = sorted(o["wireless_providers"])
        o["contacts"] = sorted(o["contacts"])
        o["consultants"] = sorted(o["consultants"])
        o["next_expiration"] = min(o.pop("expirations"), default=None)
        o["total_spend"] = round(o["total_spend"], 2)
        o["wireless_spend"] = round(o["wireless_spend"], 2)

    if enrich and leads:
        _enrich(leads, state)

    return {"state": state, "funding_year": used_fy,
            "wireless_only": wireless_only, "count": len(leads),
            "leads": leads}


def find_denied(state: str, limit: int = 15) -> dict:
    """Districts whose E-Rate data-transmission funding was DENIED — a
    documented connectivity need with no funding behind it. The pitch
    writes itself: Mission's nonprofit pricing works without E-Rate."""
    state = (state or "").strip().upper()
    fy = current_funding_year()
    rows = []
    used_fy = fy
    for try_fy in (fy, fy - 1):
        where = (f"funding_year='{try_fy}' AND state='{state}' AND "
                 "form_471_frn_status_name='Denied' AND "
                 "form_471_service_type_name='Data Transmission and/or "
                 "Internet Access'")
        select = ("ben, organization_name, organization_entity_type_name, "
                  "spin_name, cnct_email, crn_data, narrative, nickname, "
                  "total_pre_discount_costs, fcdl_comment_frn")
        try:
            rows = soda.fetch_all(config.DATASET_FRN_STATUS, where=where,
                                  select=select, order="ben")
        except Exception as e:
            log.warning("denied query failed (%s FY%s): %s", state, try_fy, e)
            rows = []
        if rows:
            used_fy = try_fy
            break
    orgs: dict[str, dict] = {}
    for r in rows:
        ben = r.get("ben")
        if not ben:
            continue
        o = orgs.setdefault(ben, {
            "org": r.get("organization_name") or "",
            "entity_type": r.get("organization_entity_type_name") or "",
            "denied_amount": 0.0, "contacts": set(), "consultants": set(),
            "reasons": [], "wanted": []})
        o["denied_amount"] += _f(r.get("total_pre_discount_costs"))
        if r.get("cnct_email"):
            o["contacts"].add(r["cnct_email"].strip().lower())
        cons = _consultant(r.get("crn_data"))
        if cons:
            o["consultants"].add(cons)
        reason = (r.get("fcdl_comment_frn") or "").strip()
        if reason and len(o["reasons"]) < 2:
            o["reasons"].append(reason[:160])
        nar = (r.get("narrative") or r.get("nickname") or "").strip()
        if nar and len(o["wanted"]) < 2:
            o["wanted"].append(nar[:120])
    leads = sorted(orgs.values(), key=lambda o: -o["denied_amount"])
    leads = leads[:max(1, min(int(limit or 15), 50))]
    for o in leads:
        o["denied_amount"] = round(o["denied_amount"], 2)
        o["contacts"] = sorted(o["contacts"])[:3]
        o["consultants"] = sorted(o["consultants"])[:2]
    return {"state": state, "funding_year": used_fy, "count": len(leads),
            "denied_leads": leads,
            "note": "Funding requests DENIED — these orgs asked for "
                    "connectivity and didn't get it funded. Angle: "
                    "Mission's nonprofit pricing works without E-Rate."}


# ---------------------------------------------------------------- internals

def _frn_rows(state: str, fy: int) -> list:
    where = (f"funding_year='{fy}' AND state='{state}' AND "
             "form_471_service_type_name='Data Transmission and/or "
             "Internet Access'")
    select = ("ben, organization_name, organization_entity_type_name, "
              "spin_name, cnct_email, crn_data, narrative, nickname, "
              "total_pre_discount_costs, contract_expiration_date")
    try:
        return soda.fetch_all(config.DATASET_FRN_STATUS, where=where,
                              select=select, order="ben")
    except Exception as e:
        log.warning("FRN lead query failed (%s FY%s): %s", state, fy, e)
        return []


def _consultant(crn: str | None) -> str | None:
    """crn_data looks like '{Name|CRN|email|phone...}' — keep name + email."""
    if not crn:
        return None
    parts = [p.strip() for p in crn.strip("{}").split("|")]
    name = parts[0] if parts else None
    email = next((p for p in parts if "@" in p), None)
    if name and email:
        return f"{name} <{email}>"
    return name or email


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _norm_district(name: str) -> str:
    n = name.upper()
    for token in ("INDEPENDENT SCHOOL DISTRICT", "INDEP SCHOOL DISTRICT",
                  "CONSOLIDATED ISD", "SCHOOL DISTRICT", "PUBLIC SCHOOLS",
                  "CISD", "ISD", "USD", "CUSD"):
        n = n.replace(token, " ")
    return re.sub(r"[^A-Z0-9]+", " ", n).strip()


def _enrich(leads: list[dict], state: str) -> None:
    """Best-effort enrollment + total budget from NCES CCD. Never raises."""
    fips = STATE_FIPS.get(state)
    if not fips:
        return
    directory = _urban_get(
        f"{URBAN_BASE}/directory/{DIRECTORY_YEAR}/?fips={fips}")
    by_norm = {}
    for d in directory:
        if d.get("lea_name"):
            by_norm.setdefault(_norm_district(d["lea_name"]), d)
    for o in leads:
        d = by_norm.get(_norm_district(o["name"]))
        if not d:
            continue
        o["enrollment"] = d.get("enrollment")
        o["city"] = d.get("city_location")
        fin = _urban_get(
            f"{URBAN_BASE}/finance/{FINANCE_YEAR}/?leaid={d.get('leaid')}")
        if fin:
            o["budget_total_expenditure"] = fin[0].get("exp_total")
            o["budget_year"] = FINANCE_YEAR


def _urban_get(url: str) -> list:
    """GET with the shared http_cache table; paginates; returns [] on error."""
    key = hashlib.sha256(url.encode()).hexdigest()
    with db.closing_conn() as conn:
        row = conn.execute(
            "SELECT fetched_at, body FROM http_cache WHERE url_hash=?",
            (key,)).fetchone()
    if row and time.time() - row["fetched_at"] < ENRICH_TTL:
        return json.loads(row["body"])
    results: list = []
    next_url = url
    try:
        for _ in range(30):   # page safety cap
            resp = httpx.get(next_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results") or [])
            next_url = data.get("next")
            if not next_url:
                break
    except Exception as e:
        log.warning("NCES enrichment fetch failed (%s): %s", url, e)
        return results
    with db.closing_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO http_cache (url_hash, url, fetched_at, "
            "body) VALUES (?, ?, ?, ?)",
            (key, url, time.time(), json.dumps(results)))
        conn.commit()
    return results
