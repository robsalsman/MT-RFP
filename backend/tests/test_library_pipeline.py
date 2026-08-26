"""Kim's library pipeline: the IMLS load, and whether promoted library
leads can actually reach her — the board listings and the Daily Run."""
import io
import json
import zipfile

import pytest

from app import competitors, dailyrun, db, libraries

CSV = (
    "FSCSKEY,LIBNAME,ADDRESS,CITY,STABR,ZIP,CNTY,PHONE,POPU_LSA,TOTINCM,"
    "TOTOPEXP,WIFISESS,GPTERMS,BKMOB\n"
    "AA0001,BIG CITY LIBRARY,1 MAIN ST,SPRINGFIELD,OH,45501,CLARK,"
    "5550001,120000,900000,850000,40000,60,2\n"
    "AA0002,SMALL TOWN LIBRARY,2 OAK AVE,SHELBY,OH,44875,RICHLAND,"
    "5550002,9000,200000,180000,3000,8,-1\n"
)


@pytest.fixture
def fake_pls(monkeypatch):
    """The PLS zip, without the download."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(libraries.AE_MEMBER, CSV)
    payload = buf.getvalue()

    class _Resp:
        content = payload

        def raise_for_status(self):
            return None

    monkeypatch.setattr(libraries.httpx, "get", lambda *a, **k: _Resp())


def test_pls_loads_into_a_brand_new_database(tmp_db, fake_pls):
    # regression: _SCHEMA created the table without `bookmobiles` while the
    # INSERT wrote it, so the very first load into a fresh DB died with
    # "table libraries has no column named bookmobiles" and Matt could
    # never produce a library lead.
    assert libraries.ensure_loaded() == 2
    with db.closing_conn() as conn:
        rows = {r["fscskey"]: dict(r) for r in
                conn.execute("SELECT * FROM libraries")}
    assert rows["AA0001"]["bookmobiles"] == 2
    assert rows["AA0001"]["name"] == "Big City Library"
    assert rows["AA0002"]["bookmobiles"] is None   # -1 is a PLS sentinel


def test_pls_backfills_a_table_that_predates_bookmobiles(tmp_db, fake_pls):
    """A DB loaded before the column existed gets it back-filled, instead
    of early-returning forever with the bookmobile boost silently dead."""
    libraries.ensure_loaded()
    with db.closing_conn() as conn:
        conn.execute("UPDATE libraries SET bookmobiles=NULL")
        conn.commit()
    libraries.ensure_loaded()
    with db.closing_conn() as conn:
        assert conn.execute(
            "SELECT bookmobiles FROM libraries WHERE fscskey='AA0001'"
        ).fetchone()[0] == 2


def _seed_board(schools=40, libs=5):
    """A realistic board: funded districts with spend, plus promoted
    zero-spend library leads."""
    contact = json.dumps([{"name": "Contact", "email": "a@b.org"}])
    with db.closing_conn() as conn:
        for i in range(schools):
            conn.execute(
                "INSERT INTO competitor_leads (ben, competitor, org, "
                "entity_type, state, spend, status, extra_contacts, source) "
                "VALUES (?,'kajeet',?,'School District','TX',?,'new',?,"
                "'erate')",
                (f"SCH{i}", f"District {i} Schools", 100000 - i, contact))
        for i in range(libs):
            conn.execute(
                "INSERT INTO competitor_leads (ben, competitor, org, "
                "entity_type, state, spend, budget, status, extra_contacts, "
                "source) VALUES (?,'greenfield',?,'Library System','OH',0,?,"
                "'new',?,'imls')",
                (f"IMLS-{i}", f"City {i} Public Library", 500000 + i,
                 contact))
        conn.commit()


def _no_slow_prep(monkeypatch):
    monkeypatch.setattr(competitors, "draft_outreach", lambda lid: {})
    monkeypatch.setattr(competitors, "find_district_contacts",
                        lambda lid: {})
    monkeypatch.setattr(competitors, "district_domain", lambda lead: None)


def test_greenfield_libraries_are_a_board_facet(tmp_db):
    _seed_board()
    summary = {s["competitor"]: s for s in competitors.summary()}
    assert summary[competitors.GREENFIELD]["accounts"] == 5
    only = competitors.list_leads(competitor=competitors.GREENFIELD)
    assert len(only) == 5
    assert only[0]["competitor_label"] == competitors.GREENFIELD_LABEL
    # zero-spend rows tie: rank them by the library's own budget
    assert [l["budget"] for l in only] == sorted(
        (l["budget"] for l in only), reverse=True)


def test_daily_run_reaches_libraries_without_a_libraries_only_focus(
        tmp_db, monkeypatch):
    # regression: candidates came off a spend-sorted page, so zero-spend
    # library leads never made the run and Kim only ever saw schools.
    _no_slow_prep(monkeypatch)
    _seed_board(schools=40, libs=10)
    assert dailyrun.get_focus() == "all"
    dailyrun.build(20, force=True)
    run = dailyrun.get_run()
    libs = [i for i in run["items"]
            if i["competitor"] == competitors.GREENFIELD_LABEL]
    assert libs, "no library lead reached the run"
    # a fixed share, so neither type can crowd the other off the run
    assert len(libs) == round(20 * dailyrun.LIBRARY_SHARE)
    assert run["total"] == 20


@pytest.mark.parametrize("schools, libs, want_libs", [
    (40, 2, 2),     # not enough libraries to fill the share
    (2, 40, 18),    # not enough districts: libraries take the rest
])
def test_a_thin_pool_on_either_side_still_fills_the_run(
        tmp_db, monkeypatch, schools, libs, want_libs):
    """The library share is a split of the run, never a cap on its size."""
    _no_slow_prep(monkeypatch)
    _seed_board(schools=schools, libs=libs)
    dailyrun.build(20, force=True)
    run = dailyrun.get_run()
    assert run["total"] == 20
    assert len([i for i in run["items"]
                if i["competitor"] == competitors.GREENFIELD_LABEL]) \
        == want_libs


def test_focus_change_refills_todays_run_and_keeps_decisions(
        tmp_db, monkeypatch):
    # regression: set_focus only wrote a kv flag, and build() early-returned
    # "already built", so flipping to libraries-only left Kim looking at the
    # schools the run had been assembled from that morning.
    _no_slow_prep(monkeypatch)
    monkeypatch.setattr(dailyrun, "refill_bg", lambda: True)  # build inline
    _seed_board()
    dailyrun.build(20, force=True)
    worked = dailyrun.get_run()["items"][0]["lead_id"]
    dailyrun.act(worked, "sent")

    dailyrun.set_focus("libraries")
    assert dailyrun.build(20) != {"already_built": True}
    run = dailyrun.get_run()
    kinds = {i["competitor"] for i in run["items"] if i["state"] == "pending"}
    assert kinds == {competitors.GREENFIELD_LABEL}
    # her decision survives the refill
    assert [i for i in run["items"] if i["lead_id"] == worked][0]["state"] \
        == "sent"


def test_focus_set_to_the_same_value_leaves_the_run_alone(
        tmp_db, monkeypatch):
    _no_slow_prep(monkeypatch)
    _seed_board()
    dailyrun.build(20, force=True)
    before = [i["lead_id"] for i in dailyrun.get_run()["items"]]
    dailyrun.set_focus("all")
    assert dailyrun.build(20) == {"already_built": True}
    assert [i["lead_id"] for i in dailyrun.get_run()["items"]] == before
