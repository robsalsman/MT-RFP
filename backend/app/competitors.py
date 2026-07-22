"""Competitor displacement engine: every district in the country paying a
Mission Telecom competitor for LTE/mobile broadband, with contacts and
ready-to-send outreach drafts.

Sweep: ONE nationwide Form 471 query per funding year (spin_name pattern
match) finds all Kajeet / Mobile Beacon / Mobile Citizen / Verizon / AT&T
mobility accounts — the org, actual annual spend, contract expiration,
filing contact, and E-Rate consultant. Results persist in competitor_leads
so Kim can work the board; sweeps upsert without clobbering her statuses
or drafted emails.

Contacts beyond the filing contact: the filing email's domain is almost
always the district's own website (jdoe@dallasisd.org -> dallasisd.org) —
we crawl a few likely staff/technology pages and have the model extract
name/title/email triples. Best-effort, on demand, never blocking the sweep.

T-Mobile is deliberately NOT a competitor here — Mission Telecom delivers
on T-Mobile's network.
"""
import datetime
import json
import logging
import re

import httpx

from . import ai, config, db, leads as leads_mod, soda

log = logging.getLogger(__name__)

# competitor key -> label, tier, and SODA upper(spin_name) LIKE patterns
COMPETITORS = {
    "kajeet": {"label": "Kajeet", "tier": "K-12 specialist",
               "patterns": ["%KAJEET%"]},
    "mobile_beacon": {"label": "Mobile Beacon", "tier": "K-12 specialist",
                      "patterns": ["%MOBILE BEACON%"]},
    "mobile_citizen": {"label": "Mobile Citizen", "tier": "K-12 specialist",
                       "patterns": ["%MOBILE CITIZEN%"]},
    "verizon": {"label": "Verizon Wireless", "tier": "carrier",
                "patterns": ["%CELLCO%", "%VERIZON WIRELESS%"]},
    "att": {"label": "AT&T Mobility", "tier": "carrier",
            "patterns": ["%AT&T MOBILITY%"]},
}

# consultant/vendor email domains that are NOT the district's own website
_NON_DISTRICT_DOMAINS = (
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com",
    "erate", "e-rate", "consult", "funds", "kelloggllc", "csmcentral",
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def competitor_for_spin(spin: str) -> str | None:
    s = (spin or "").upper()
    for key, c in COMPETITORS.items():
        for p in c["patterns"]:
            if p.strip("%") in s:
                return key
    return None


def _soda_where(fy: int) -> str:
    pats = [p for c in COMPETITORS.values() for p in c["patterns"]]
    likes = " OR ".join(f"upper(spin_name) like '{p}'" for p in pats)
    return f"funding_year='{fy}' AND ({likes})"


def sweep() -> dict:
    """Nationwide competitor sweep. Upserts competitor_leads; preserves
    Kim's per-lead status / drafts / found contacts. Returns a summary."""
    fy = leads_mod.current_funding_year()
    select = ("ben, organization_name, organization_entity_type_name, state, "
              "spin_name, cnct_email, crn_data, narrative, nickname, "
              "total_pre_discount_costs, contract_expiration_date")
    rows = soda.fetch_all(config.DATASET_FRN_STATUS, where=_soda_where(fy),
                          select=select, order="ben")
    used_fy = fy
    prev = soda.fetch_all(config.DATASET_FRN_STATUS,
                          where=_soda_where(fy - 1), select=select,
                          order="ben")
    if len(prev) > len(rows):
        used_fy, rows = fy - 1, prev

    agg: dict[tuple, dict] = {}
    for r in rows:
        comp = competitor_for_spin(r.get("spin_name"))
        ben = r.get("ben")
        if not comp or not ben:
            continue
        o = agg.setdefault((ben, comp), {
            "org": r.get("organization_name") or "",
            "entity_type": r.get("organization_entity_type_name") or "",
            "state": r.get("state") or "",
            "spend": 0.0, "spins": set(), "contacts": set(),
            "consultants": set(), "narratives": [], "expirations": [],
        })
        o["spend"] += leads_mod._f(r.get("total_pre_discount_costs"))
        if r.get("spin_name"):
            o["spins"].add(r["spin_name"].strip())
        if r.get("cnct_email"):
            o["contacts"].add(r["cnct_email"].strip().lower())
        cons = leads_mod._consultant(r.get("crn_data"))
        if cons:
            o["consultants"].add(cons)
        exp = (r.get("contract_expiration_date") or "")[:10]
        if exp:
            o["expirations"].append(exp)
        nar = (r.get("narrative") or r.get("nickname") or "").strip()
        if nar and len(o["narratives"]) < 3:
            o["narratives"].append(nar[:140])

    now = datetime.datetime.utcnow().isoformat(timespec="seconds")
    upserted = 0
    with db.closing_conn() as conn:
        for (ben, comp), o in agg.items():
            conn.execute(
                """INSERT INTO competitor_leads
                   (ben, competitor, funding_year, org, entity_type, state,
                    spins, spend, next_expiration, contacts, consultants,
                    narratives, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(ben, competitor) DO UPDATE SET
                     funding_year=excluded.funding_year,
                     org=excluded.org, entity_type=excluded.entity_type,
                     state=excluded.state, spins=excluded.spins,
                     spend=excluded.spend,
                     next_expiration=excluded.next_expiration,
                     contacts=excluded.contacts,
                     consultants=excluded.consultants,
                     narratives=excluded.narratives,
                     updated_at=excluded.updated_at""",
                (ben, comp, used_fy, o["org"], o["entity_type"], o["state"],
                 json.dumps(sorted(o["spins"])), round(o["spend"], 2),
                 min(o["expirations"], default=None),
                 json.dumps(sorted(o["contacts"])),
                 json.dumps(sorted(o["consultants"])),
                 json.dumps(o["narratives"]), now))
            upserted += 1
        conn.commit()
    log.info("competitor sweep FY%s: %d accounts", used_fy, upserted)
    return {"funding_year": used_fy, "accounts": upserted,
            "summary": summary()}


def summary() -> list[dict]:
    with db.closing_conn() as conn:
        rows = conn.execute(
            """SELECT competitor, COUNT(*) n, ROUND(SUM(spend),2) total,
                      SUM(status='contacted') contacted
               FROM competitor_leads WHERE status != 'dismissed'
               GROUP BY competitor ORDER BY total DESC""").fetchall()
    return [{"competitor": r["competitor"],
             "label": COMPETITORS.get(r["competitor"], {}).get(
                 "label", r["competitor"]),
             "accounts": r["n"], "total_spend": r["total"],
             "contacted": r["contacted"] or 0} for r in rows]


def list_leads(competitor: str | None = None, state: str | None = None,
               status: str | None = None, min_spend: float = 0,
               sort: str = "spend", limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM competitor_leads WHERE 1=1"
    params: list = []
    if competitor:
        sql += " AND competitor=?"
        params.append(competitor)
    if state:
        sql += " AND state=?"
        params.append(state.upper())
    if status:
        sql += " AND status=?"
        params.append(status)
    else:
        sql += " AND status != 'dismissed'"
    if min_spend:
        sql += " AND spend >= ?"
        params.append(float(min_spend))
    if sort == "expiration":
        sql += " ORDER BY next_expiration ASC"
    elif sort == "competitor":
        # group by competitor, biggest spend first within each group
        sql += " ORDER BY competitor ASC, spend DESC"
    else:
        sql += " ORDER BY spend DESC"
    sql += " LIMIT ?"
    params.append(max(1, min(int(limit or 50), 200)))
    with db.closing_conn() as conn:
        rows = [dict(r) for r in conn.execute(sql, params)]
    for r in rows:
        for f in ("spins", "contacts", "consultants", "narratives",
                  "extra_contacts"):
            try:
                r[f] = json.loads(r.get(f) or "[]")
            except (TypeError, json.JSONDecodeError):
                r[f] = []
        r["competitor_label"] = COMPETITORS.get(
            r["competitor"], {}).get("label", r["competitor"])
    return rows


def get_lead(lead_id: int) -> dict | None:
    with db.closing_conn() as conn:
        row = conn.execute("SELECT * FROM competitor_leads WHERE id=?",
                           (lead_id,)).fetchone()
    if not row:
        return None
    r = dict(row)
    for f in ("spins", "contacts", "consultants", "narratives",
              "extra_contacts"):
        try:
            r[f] = json.loads(r.get(f) or "[]")
        except (TypeError, json.JSONDecodeError):
            r[f] = []
    r["competitor_label"] = COMPETITORS.get(
        r["competitor"], {}).get("label", r["competitor"])
    return r


def set_status(lead_id: int, status: str) -> bool:
    if status not in ("new", "contacted", "dismissed"):
        return False
    with db.closing_conn() as conn:
        cur = conn.execute("UPDATE competitor_leads SET status=? WHERE id=?",
                           (status, lead_id))
        conn.commit()
        return cur.rowcount > 0


# ------------------------------------------------- contact enrichment

def district_domain(lead: dict) -> str | None:
    """The filing contact's email domain is usually the district's website."""
    for email in lead.get("contacts", []):
        dom = email.split("@")[-1].lower()
        if not any(x in dom for x in _NON_DISTRICT_DOMAINS):
            return dom
    return None


def find_district_contacts(lead_id: int) -> dict:
    """Crawl the district's site (from the filing email domain) for staff
    contacts — tech director, superintendent. Best-effort public data."""
    lead = get_lead(lead_id)
    if not lead:
        return {"error": "no such lead"}
    dom = district_domain(lead)
    if not dom:
        return {"error": "no district-domain email on file; only consultant "
                         "contacts available", "contacts": []}
    pages = _fetch_site_pages(dom)
    if not pages:
        return {"error": f"couldn't reach www.{dom}", "contacts": []}
    text = "\n\n".join(pages.values())[:24000]
    extracted = _extract_contacts(text, lead["org"])
    # always include any raw emails on the pages the model may have missed
    seen = {c.get("email") for c in extracted}
    for em in set(_EMAIL_RE.findall(text)):
        if em.lower().endswith(dom) and em not in seen and len(extracted) < 12:
            extracted.append({"name": None, "title": None, "email": em})
    with db.closing_conn() as conn:
        conn.execute("UPDATE competitor_leads SET extra_contacts=? WHERE id=?",
                     (json.dumps(extracted), lead_id))
        conn.commit()
    return {"domain": dom, "pages_read": list(pages.keys()),
            "contacts": extracted}


def _fetch_site_pages(dom: str) -> dict[str, str]:
    """Homepage + up to 3 likely staff/technology pages, text-stripped."""
    out: dict[str, str] = {}
    base_candidates = [f"https://www.{dom}", f"https://{dom}"]
    home_html = None
    base = None
    for b in base_candidates:
        try:
            resp = httpx.get(b, timeout=12, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code < 400:
                home_html, base = resp.text, str(resp.url).rstrip("/")
                break
        except Exception:
            continue
    if not home_html:
        return out
    out["home"] = _strip_html(home_html)[:8000]
    # follow links whose text/href suggests staff or technology pages
    links = re.findall(r'href=["\']([^"\'#]+)["\']', home_html, re.I)
    picks = []
    for href in links:
        h = href.lower()
        if any(k in h for k in ("staff", "directory", "technology", "depart",
                                "administration", "contact")):
            url = href if h.startswith("http") else f"{base}/{href.lstrip('/')}"
            if dom in url and url not in picks:
                picks.append(url)
        if len(picks) >= 3:
            break
    for url in picks:
        try:
            resp = httpx.get(url, timeout=12, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code < 400:
                out[url] = _strip_html(resp.text)[:8000]
        except Exception:
            continue
    return out


def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                  flags=re.DOTALL | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def _extract_contacts(text: str, org: str) -> list[dict]:
    raw = ai._chat(
        "You extract staff contacts from school-district website text. "
        "Return ONLY a JSON array (no prose) of up to 8 objects with keys "
        "name, title, email (null when unknown). Prefer technology "
        "directors, CTOs, superintendents, business/purchasing officials. "
        "Never invent emails — only ones present in the text.",
        f"District: {org}\n\nWebsite text:\n{text}", max_tokens=1500)
    if not raw:
        return []
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for i in items:
        if not isinstance(i, dict):
            continue
        em = (i.get("email") or "").lower()
        # drop placeholder/system addresses sites embed in markup
        if em and any(b in em for b in ("null", "noreply", "no-reply",
                                        "example", "webmaster", "postmaster")):
            i["email"] = None
        out.append(i)
    return out[:8]


# ------------------------------------------------- outreach drafting

def draft_outreach(lead_id: int) -> dict:
    """Draft Kim's cold email for one competitor account, from real data."""
    lead = get_lead(lead_id)
    if not lead:
        return {"error": "no such lead"}
    best = _best_contact(lead)
    comp = lead["competitor_label"]
    facts = [
        f"District/org: {lead['org']} ({lead['state']})",
        f"They currently pay {comp} about ${lead['spend']:,.0f}/year for "
        f"mobile broadband (public E-Rate Form 471 data, "
        f"FY{lead['funding_year']}).",
    ]
    if lead.get("next_expiration"):
        facts.append(f"That contract expires {lead['next_expiration']}.")
    if lead.get("enrollment"):
        facts.append(f"Enrollment: ~{lead['enrollment']:,} students.")
    if lead.get("budget"):
        facts.append(f"Total district budget: ${lead['budget']:,.0f}.")
    if lead.get("narratives"):
        facts.append(f"Their filing describes: {lead['narratives'][0]}")
    if best.get("name"):
        facts.append(f"Recipient: {best['name']}"
                     + (f", {best['title']}" if best.get("title") else ""))
    raw = ai._chat(
        "You write short cold-outreach emails for Kim, an account "
        "executive at Mission Telecom — a NONPROFIT wireless ISP on the "
        "T-Mobile network selling LTE/5G mobile broadband and hotspot "
        "lending to schools and libraries, E-Rate eligible, plans from "
        "$20-25/line/month with free CIPA-compliant filtering. "
        "Rules: under 160 words. Plain text. Subject line first. Use ONLY "
        "the facts provided — never invent names, numbers, or claims. "
        "Cite their real current spend and provider. If no recipient name "
        "is given, open with a neutral greeting. Tone: helpful peer, not "
        "salesy. End with a specific ask for a 15-minute call. Sign as "
        "Kim, Mission Telecom.",
        "Facts:\n- " + "\n- ".join(facts), max_tokens=1200)
    if not raw:
        return {"error": "draft generation failed — try again"}
    draft = raw.strip()
    with db.closing_conn() as conn:
        conn.execute("UPDATE competitor_leads SET email_draft=? WHERE id=?",
                     (draft, lead_id))
        conn.commit()
    return {"draft": draft, "to": best.get("email"),
            "to_name": best.get("name"), "lead_id": lead_id}


def _best_contact(lead: dict) -> dict:
    """Named district staff (from enrichment) beats the bare filing email."""
    for c in lead.get("extra_contacts", []):
        title = (c.get("title") or "").lower()
        if c.get("email") and any(k in title for k in
                                  ("tech", "cto", "superintend", "cio")):
            return c
    for c in lead.get("extra_contacts", []):
        if c.get("email"):
            return c
    emails = lead.get("contacts", [])
    return {"email": emails[0] if emails else None}
