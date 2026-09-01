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


def test_libraries_only_filter_reaches_every_kind_of_library(tmp_db):
    """Kim's switch: promoted IMLS systems AND the library systems already
    on the funding board, and nothing else."""
    _seed_board(schools=5, libs=3)
    with db.closing_conn() as conn:
        conn.execute(
            "INSERT INTO competitor_leads (ben, competitor, org, "
            "entity_type, state, spend, status, source) VALUES "
            "('B1','kajeet','Springfield City Library','Library','OH',"
            "9000,'new','erate')")
        conn.execute(   # E-Rate files some systems under a bare type
            "INSERT INTO competitor_leads (ben, competitor, org, "
            "entity_type, state, spend, status, source) VALUES "
            "('B2','verizon','Athens County Public Libraries','Consortium',"
            "'OH',8000,'new','erate')")
        conn.commit()
    orgs = {l["org"] for l in competitors.list_leads(libraries_only=True,
                                                     limit=100)}
    assert orgs == {"City 0 Public Library", "City 1 Public Library",
                    "City 2 Public Library", "Springfield City Library",
                    "Athens County Public Libraries"}
    # and it composes with the other filters
    assert not competitors.list_leads(libraries_only=True, state="TX")


def test_daily_run_serves_only_libraries_when_kim_says_so(
        tmp_db, monkeypatch):
    # regression: candidates came off a spend-sorted page, so zero-spend
    # library leads never made the run at all — even under this focus.
    _no_slow_prep(monkeypatch)
    _seed_board(schools=40, libs=10)
    dailyrun.set_focus("libraries", rebuild=False)
    dailyrun.build(20, force=True)
    run = dailyrun.get_run()
    assert run["total"] == 10
    assert {i["competitor"] for i in run["items"]} \
        == {competitors.GREENFIELD_LABEL}


def test_daily_run_can_reach_a_library_under_the_all_focus(
        tmp_db, monkeypatch):
    """'all' means all: score decides the order, but a zero-spend library
    has to be in the running at all."""
    _no_slow_prep(monkeypatch)
    _seed_board(schools=2, libs=10)
    assert dailyrun.get_focus() == "all"
    dailyrun.build(20, force=True)
    run = dailyrun.get_run()
    assert [i for i in run["items"]
            if i["competitor"] == competitors.GREENFIELD_LABEL]


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


# --- what Matt can actually be asked to do in chat -------------------------

def _tool(name):
    from app import chat
    return next(t["function"] for t in chat.TOOLS
                if t["function"]["name"] == name)


def test_matt_can_set_and_read_the_run_focus_from_chat(tmp_db, monkeypatch):
    """Kim's 'libraries only, no more schools' has to be something Matt can
    carry out — and undo — without anyone opening Settings."""
    from app import chat
    monkeypatch.setattr(dailyrun, "refill_bg", lambda: True)
    assert _tool("daily_run_focus")["parameters"]["properties"]["focus"][
        "enum"] == ["all", "libraries"]

    assert chat._exec_tool("daily_run_focus", {}) == {"focus": "all"}

    r = chat._exec_tool("daily_run_focus", {"focus": "libraries"})
    assert r["focus"] == "libraries" and r["refilling"] is True
    assert dailyrun.get_focus() == "libraries"

    # asking again is a no-op, not a pointless rebuild
    assert chat._exec_tool(
        "daily_run_focus", {"focus": "libraries"})["refilling"] is False
    # and she can put it back
    assert chat._exec_tool(
        "daily_run_focus", {"focus": "all"})["focus"] == "all"


def test_matt_can_list_libraries_only_from_chat(tmp_db, monkeypatch):
    from app import chat
    monkeypatch.setattr(competitors, "district_domain", lambda lead: None)
    _seed_board(schools=40, libs=3)
    assert "libraries_only" in \
        _tool("competitor_accounts")["parameters"]["properties"]
    r = chat._exec_tool("competitor_accounts",
                        {"libraries_only": True, "limit": 10})
    assert r["accounts"]
    assert all("Library" in a["org"] for a in r["accounts"])
