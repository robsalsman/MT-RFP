"""Every US public library system, from the IMLS Public Libraries Survey
(FY2022 public-use file): name, address, zip, county, phone, population
served, total income/operating expenditure, wifi sessions. ~9k systems.

This is Mission Telecom's Project: Volume Up target universe. Targets are
ranked by local need (households that lost ACP in their zip) and budget,
and flagged when they already appear on the competitor board (existing
LTE buyer = displacement; absent = greenfield hotspot-lending pitch).

Note: the FY2022 file has no hotspot-lending count (IMLS added that item
in later vintages) — lending status comes from our funding-data board
instead.
"""
import csv
import io
import json
import logging
import re
import zipfile

import httpx

from . import db

log = logging.getLogger(__name__)

PLS_ZIP = ("https://imls.gov/sites/default/files/2024-06/"
           "pls_fy2022_csv.zip")
AE_MEMBER = "PLS_FY2022 PUD_CSV/PLS_FY22_AE_pud22i.csv"

_SCHEMA = """CREATE TABLE IF NOT EXISTS libraries (
    fscskey TEXT PRIMARY KEY,
    name TEXT, address TEXT, city TEXT, state TEXT, zip TEXT,
    county TEXT, phone TEXT,
    population INTEGER, total_income REAL, operating_exp REAL,
    wifi_sessions INTEGER, terminals INTEGER, bookmobiles INTEGER
);"""


def _migrate():
    """Add the bookmobile column to a table created before it existed.
    (New databases get it from _SCHEMA — it must be in both, or the first
    load into a fresh DB fails on the INSERT.)"""
    with db.closing_conn() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(libraries)")}
        if cols and "bookmobiles" not in cols:
            conn.execute(
                "ALTER TABLE libraries ADD COLUMN bookmobiles INTEGER")
        conn.commit()


def ensure_loaded() -> int:
    _migrate()
    with db.closing_conn() as conn:
        conn.execute(_SCHEMA)
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM libraries").fetchone()[0]
        # A DB loaded before the bookmobile column existed has the column
        # but no values in it — re-read the file once to fill it, or the
        # bookmobile boost silently never fires.
        filled = n and conn.execute(
            "SELECT COUNT(*) FROM libraries WHERE bookmobiles IS NOT NULL"
        ).fetchone()[0]
    if n > 5000 and filled:
        return n
    try:
        r = httpx.get(PLS_ZIP, headers={"User-Agent": "Mozilla/5.0"},
                      timeout=300, follow_redirects=True)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        f = z.open(AE_MEMBER)
    except Exception as e:
        log.warning("PLS download failed: %s", e)
        return n

    def num(v, cast=int):
        try:
            x = cast(float(v))
            return x if x >= 0 else None   # PLS uses negative sentinels
        except (TypeError, ValueError):
            return None

    rows = []
    reader = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"))
    for d in reader:
        if not d.get("FSCSKEY"):
            continue
        rows.append((
            d["FSCSKEY"], (d.get("LIBNAME") or "").title(),
            (d.get("ADDRESS") or "").title(),
            (d.get("CITY") or "").title(),
            d.get("STABR") or "", (d.get("ZIP") or "")[:5],
            (d.get("CNTY") or "").title(), d.get("PHONE") or "",
            num(d.get("POPU_LSA")), num(d.get("TOTINCM"), float),
            num(d.get("TOTOPEXP"), float), num(d.get("WIFISESS")),
            num(d.get("GPTERMS")), num(d.get("BKMOB"))))
    with db.closing_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO libraries (fscskey, name, address, "
            "city, state, zip, county, phone, population, total_income, "
            "operating_exp, wifi_sessions, terminals, bookmobiles) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM libraries").fetchone()[0]
    log.info("PLS loaded: %d library systems", n)
    return n


def promote_to_leads(state: str | None = None, n: int = 25) -> dict:
    """Turn IMLS library-universe rows into WORKABLE leads: greenfield
    entries on the board (competitor='greenfield') that flow through the
    Daily Run, drafts, LinkedIn queue — everything. Contacts/website come
    from the USAC E-Rate entity directory when a match is found.

    Ranked by need: households that lost ACP in their zip, then budget.
    Bookmobile systems get a boost — rolling hotspots are the perfect
    LTE story. Skips libraries already promoted or already on the board."""
    from . import acp, competitors, soda, config as cfg
    import datetime
    ensure_loaded()
    _migrate()
    acp.ensure_loaded()
    with db.closing_conn() as conn:
        sql = ("SELECT l.*, COALESCE(a.households,0) hh FROM libraries l "
               "LEFT JOIN acp_zip a ON a.zip=l.zip WHERE "
               "COALESCE(l.operating_exp,0) > 50000 AND "
               "l.fscskey NOT IN (SELECT REPLACE(ben,'IMLS-','') FROM "
               "competitor_leads WHERE ben LIKE 'IMLS-%')")
        params: list = []
        if state:
            sql += " AND l.state=?"
            params.append(state.upper())
        libs = [dict(r) for r in conn.execute(sql, params)]
        # don't re-add libraries already on the board via funding data
        board_zips = {r[0] for r in conn.execute(
            "SELECT DISTINCT zip FROM competitor_leads WHERE zip IS NOT "
            "NULL AND (entity_type LIKE '%ibrar%' OR org LIKE '%LIBRAR%')")}
    libs = [l for l in libs if l["zip"] not in board_zips]
    libs.sort(key=lambda x: ((x["hh"] or 0)
                             + (50000 if (x.get("bookmobiles") or 0) else 0),
                             x["operating_exp"] or 0), reverse=True)
    picked = libs[:max(1, min(int(n or 25), 100))]
    now = datetime.datetime.utcnow().isoformat(timespec="seconds")
    created = 0
    for lib in picked:
        # try to find their E-Rate entity (website + contact email)
        website = email = cname = None
        ben = f"IMLS-{lib['fscskey']}"
        try:
            words = "".join(ch if ch.isalnum() or ch == " " else " "
                            for ch in lib["name"].upper()).split()[:3]
            ents = soda.fetch_all(
                cfg.DATASET_ENTITY,
                where=("upper(entity_name) like '%"
                       + " ".join(words).replace("'", "") + "%' AND "
                       f"physical_state='{lib['state']}'"),
                select="entity_number, entity_name, website_url, "
                       "general_contact_name, general_contact_email",
                order="entity_number")
            if ents:
                e = ents[0]
                ben = str(e.get("entity_number") or ben)
                website = e.get("website_url")
                email = (e.get("general_contact_email") or "").strip().lower() or None
                cname = (e.get("general_contact_name") or "").strip() or None
        except Exception as e:
            log.debug("entity match failed for %s: %s", lib["name"], e)
        contacts = []
        if email:
            contacts.append(f"{cname} <{email}>" if cname else email)
        note = (f"IMLS library system: serves {lib['population'] or '?'} "
                f"people; budget ${lib['operating_exp'] or 0:,.0f}"
                + (f"; {lib['bookmobiles']} bookmobile(s)"
                   if lib.get("bookmobiles") else "")
                + (f"; {lib['hh']:,} households in zip lost ACP"
                   if lib["hh"] else "")
                + (f"; phone {lib['phone']}" if lib["phone"] else ""))
        with db.closing_conn() as conn:
            cur = conn.execute(
                """INSERT INTO competitor_leads
                   (ben, competitor, funding_year, org, entity_type, state,
                    city, zip, website, spins, spend, budget, contacts,
                    consultants, narratives, updated_at, source)
                   VALUES (?,'greenfield',NULL,?,?,?,?,?,?,'[]',0,?,?,
                           '[]',?,?,'imls')
                   ON CONFLICT(ben, competitor) DO NOTHING""",
                (ben, lib["name"], "Library System", lib["state"],
                 lib["city"], lib["zip"], website,
                 lib["operating_exp"], json.dumps(contacts),
                 json.dumps([note]), now))
            conn.commit()
            created += cur.rowcount
    return {"promoted": created, "considered": len(libs),
            "state": state or "ALL",
            "note": "Greenfield library leads added to the board — they "
                    "flow through the Daily Run, drafts, and the LinkedIn "
                    "queue like any other lead."}


def find_targets(state: str, min_population: int = 0,
                 limit: int = 15) -> dict:
    """Library targets for hotspot lending, ranked by ACP-loss need then
    budget. on_board = already buying from a tracked competitor."""
    from . import acp
    ensure_loaded()
    acp.ensure_loaded()
    state = (state or "").strip().upper()
    with db.closing_conn() as conn:
        libs = [dict(r) for r in conn.execute(
            "SELECT * FROM libraries WHERE state=? AND "
            "COALESCE(population,0) >= ? ORDER BY "
            "COALESCE(operating_exp,0) DESC LIMIT 400",
            (state, int(min_population or 0)))]
        board_zips = {r[0] for r in conn.execute(
            "SELECT DISTINCT zip FROM competitor_leads WHERE state=? AND "
            "zip IS NOT NULL AND (entity_type LIKE '%ibrar%' OR org LIKE "
            "'%LIBRAR%')", (state,))}
        for lib in libs:
            row = conn.execute("SELECT households FROM acp_zip WHERE zip=?",
                               (lib["zip"],)).fetchone()
            lib["acp_households_lost"] = row[0] if row else 0
            lib["on_board"] = lib["zip"] in board_zips
    libs.sort(key=lambda x: (x["acp_households_lost"] or 0,
                             x["operating_exp"] or 0), reverse=True)
    libs = libs[:max(1, min(int(limit or 15), 50))]
    return {"state": state, "count": len(libs), "libraries": libs,
            "note": "Ranked by households that lost ACP in the library's "
                    "zip (local need), then budget. on_board=true means "
                    "they already buy from a tracked competitor "
                    "(displacement); false = greenfield Project: Volume Up "
                    "pitch."}


# --------------------------------------------------------- website scan

_WORD_PAGE_HINTS = ("hotspot", "hot-spot", "wifi", "wi-fi", "internet",
                    "lending", "borrow", "checkout", "check-out", "tech",
                    "technology", "services", "digital", "equity")


def _domain_for(lead: dict) -> str | None:
    """The library's own web domain: the website we stored at promotion,
    else the contact email's domain."""
    from . import competitors
    site = (lead.get("website") or "").strip()
    if site:
        dom = re.sub(r"^https?://", "", site).split("/")[0].strip()
        dom = dom.split("@")[-1].lower().lstrip("www.")
        if "." in dom:
            return dom
    return competitors.district_domain(lead)


def _find_domain(lead: dict) -> str | None:
    """No site on file — ask the web for one, the way a person would."""
    from . import mentions
    q = " ".join(x for x in (lead.get("org"), lead.get("city"),
                             lead.get("state"), "library") if x)
    try:
        hits = mentions.web_search(q, limit=4)
    except Exception as e:
        log.debug("domain lookup failed for %s: %s", lead.get("org"), e)
        return None
    for h in hits:
        dom = re.sub(r"^https?://", "", h.get("url") or "").split("/")[0]
        dom = dom.lower().lstrip("www.")
        # skip directories and aggregators — we want their own site
        if dom and "." in dom and not any(
                b in dom for b in ("facebook.", "wikipedia.", "yelp.",
                                   "linkedin.", "instagram.", "twitter.",
                                   "x.com", "youtube.", "imls.gov",
                                   "publiclibraries.com", "librarytechnology",
                                   "usa.gov", "google.")):
            return dom
    return None


def _pages_mentioning(dom: str, term: str) -> dict:
    """Does this library's site say `term`, and where? Returns
    {status, hits:[{url, snippet, from}]}.

    Search first, crawl second. Most library sites render their pages
    with JavaScript, so fetching the HTML sees a near-empty shell — a
    search engine has already read what a crawler can't. The crawl is the
    fallback for the server-rendered sites (and for when no search key is
    configured).
    """
    from . import mentions
    from .competitors import _strip_html
    tl = term.lower()
    hits: list[dict] = []

    def grab(url: str):
        try:
            r = httpx.get(url, timeout=12, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code >= 400:
                return None
            return str(r.url).rstrip("/"), r.text
        except Exception:
            return None

    def quote(text: str) -> str | None:
        i = text.lower().find(tl)
        if i < 0:
            return None
        return " ".join(text[max(0, i - 120):i + 200].split())[:300]

    # 1. ask the index what the whole site says
    try:
        found = mentions.web_search(f"site:{dom} {term}", limit=5)
    except Exception as e:
        log.debug("site search failed for %s: %s", dom, e)
        found = []
    for f in found[:3]:
        url = f.get("url") or ""
        if dom not in url:
            continue
        page = grab(url)
        q = quote(_strip_html(page[1])) if page else None
        if q:                       # confirmed on the page itself
            hits.append({"url": page[0], "snippet": q, "from": "page"})
        elif tl in (f.get("snippet", "") + f.get("title", "")).lower():
            # the page is script-rendered: report the index's words, and
            # say so, rather than claiming we read the page
            hits.append({"url": url, "from": "search result",
                         "snippet": (f.get("snippet") or "")[:300]})
        if len(hits) >= 3:
            break
    if hits:
        return {"status": "found", "hits": hits}

    # 2. no search hit — read the site ourselves
    home = None
    for b in (f"https://www.{dom}", f"https://{dom}"):
        home = grab(b)
        if home:
            break
    if not home:
        return {"status": "unreachable", "hits": []}
    base, home_html = home
    q = quote(_strip_html(home_html))
    if q:
        hits.append({"url": base, "snippet": q, "from": "page"})
    anchors = re.findall(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>',
                         home_html, re.I | re.S)
    picks: list[str] = []
    for href, txt in anchors:
        blob = (href + " " + re.sub(r"<[^>]+>", "", txt)).lower()
        if any(k in blob for k in _WORD_PAGE_HINTS) or tl in blob:
            url = (href if href.lower().startswith("http")
                   else f"{base}/{href.lstrip('/')}")
            if dom in url and url not in picks:
                picks.append(url)
        if len(picks) >= 5:
            break
    for url in picks:
        if len(hits) >= 3:
            break
        page = grab(url)
        if not page:
            continue
        q = quote(_strip_html(page[1]))
        if q:
            hits.append({"url": page[0], "snippet": q, "from": "page"})
    if hits:
        return {"status": "found", "hits": hits}
    # a site whose HTML carries almost no text is a JS shell: we did not
    # read it, so we must not report it as "doesn't mention it"
    readable = len(_strip_html(home_html)) > 1500 or len(anchors) > 5
    return {"status": "no mention" if readable else "unreadable", "hits": []}


def scan_sites(term: str, state: str | None = None, limit: int = 12,
               find_missing_sites: bool = True) -> dict:
    """Which of Kim's libraries actually say `term` on their own website.

    Reads the library rows on the board (promoted IMLS systems and the
    library systems in the funding data), visits each library's real site
    and reports the ones whose pages contain the word, with the sentence
    it appears in. A library already talking about hotspot lending is a
    warm prospect, not a cold one."""
    from concurrent.futures import ThreadPoolExecutor
    from . import competitors
    term = (term or "").strip()
    if not term:
        return {"error": "give me a word to look for, e.g. 'hotspot'"}
    n = max(1, min(int(limit or 12), 40))
    leads = competitors.list_leads(libraries_only=True, state=state,
                                   status="all", limit=200)
    leads = [l for l in leads if (l.get("status") or "new") != "dismissed"]
    candidates = leads[:n * 3]      # room for the ones with no site at all

    def one(lead: dict) -> dict:
        dom = _domain_for(lead)
        if not dom and find_missing_sites:
            dom = _find_domain(lead)
        if not dom:
            return {"lead": lead, "dom": None, "status": "no website",
                    "hits": []}
        r = _pages_mentioning(dom, term)
        return {"lead": lead, "dom": dom, **r}

    with ThreadPoolExecutor(max_workers=8) as pool:
        scanned = list(pool.map(one, candidates[:n]))

    matches, no_site, unreadable, clear = [], [], [], 0
    for r in scanned:
        lead = r["lead"]
        if r["status"] == "no website":
            no_site.append(lead["org"])
        elif r["status"] in ("unreadable", "unreachable"):
            unreadable.append(lead["org"])
        elif r["hits"]:
            matches.append({
                "lead_id": lead["id"], "org": lead["org"],
                "state": lead["state"], "city": lead.get("city"),
                "website": r["dom"],
                "pages": [h["url"] for h in r["hits"]][:3],
                "quote": r["hits"][0]["snippet"],
                "evidence": r["hits"][0]["from"]})
        else:
            clear += 1

    from . import config as cfg
    searched = len(matches) + clear
    note = (f"{len(matches)} of {searched} libraries we could actually read "
            f"say '{term}' on their own site — they are already talking "
            "about it publicly, so they're warm, not cold.")
    if unreadable:
        note += (f" {len(unreadable)} more could not be read (their pages "
                 "are built by JavaScript) — that is unknown, NOT a no.")
    if no_site:
        note += (f" {len(no_site)} have no website on file.")
    if not cfg.BRAVE_API_KEY:
        note += (" NOTE: no BRAVE_API_KEY is set, so this fell back to "
                 "reading pages directly and will miss a lot — set the key "
                 "for real coverage.")
    if not searched and not unreadable and not no_site:
        note = ("No library leads on the board to read. Promote some first "
                "with get_more_library_leads.")
    return {"term": term, "state": state or "ALL",
            "libraries_read": searched, "matches": matches,
            "could_not_read": unreadable[:10],
            "no_website_on_file": no_site[:10],
            "note": note}
