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


def ensure_loaded() -> int:
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
            num(d.get("GPTERMS"))))
    with db.closing_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO libraries VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM libraries").fetchone()[0]
    log.info("PLS loaded: %d library systems", n)
    return n


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
