"""Closing machine: savings math, objection classifier, E-Rate clock,
stage rules."""
import datetime

from app.closing import _classify
from app.competitors import ENGAGED, STAGES, STALE_AFTER
from app.savings import compute_savings, erate_sign_by


def test_savings_with_devices():
    sv = compute_savings({"spend": 946400, "devices": 2000, "source": "erate"})
    assert sv["current_per_line"] == round(946400 / 12 / 2000, 2)
    assert sv["mission_annual_low"] == 2000 * 12 * 20
    assert sv["savings_high"] == 946400 - 2000 * 12 * 20
    assert not sv["estimated"]


def test_savings_without_devices_is_labeled_estimate():
    sv = compute_savings({"spend": 100000, "devices": None, "source": "erate"})
    assert sv["estimated"]
    assert 0 < sv["savings_low"] < sv["savings_high"] < 100000


def test_ecf_spend_is_not_annualized():
    sv = compute_savings({"spend": 48000, "devices": 100, "source": "ecf"})
    assert sv["current_annual"] is None
    assert sv["ecf_total"] == 48000


def test_objection_classifier():
    assert _classify("This looks too expensive for our budget") == "price"
    assert _classify("We're under contract with Kajeet until 2027") \
        == "under_contract"
    assert _classify("Does T-Mobile even have signal out here?") == "coverage"
    assert _classify("We'd need to run an RFP through the board") \
        == "procurement"
    assert _classify("Maybe revisit next year") == "timing"


def test_stage_machinery():
    assert set(STALE_AFTER) == set(ENGAGED)
    for s in ("won", "lost", "new", "dismissed"):
        assert s in STAGES and s not in ENGAGED


def test_erate_clock_orders_correctly():
    cal = erate_sign_by()
    assert datetime.date.fromisoformat(cal["post_470_by"]) < \
        datetime.date.fromisoformat(cal["form_471_window_closes"])
    assert cal["next_funding_year"] >= 2026
