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
    wifi_sessions INTEGER, terminals INTEGER
);"""


def _migrate():
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
    if n > 5000:
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
