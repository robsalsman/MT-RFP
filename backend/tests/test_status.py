"""28-day bid-window math."""
from datetime import date

from app import status


def test_acd_from_usac_wins_over_computed():
    assert status.allowable_contract_date(
        date(2026, 7, 1), date(2026, 8, 15)) == date(2026, 8, 15)


def test_acd_computed_as_certified_plus_28():
    assert status.allowable_contract_date(date(2026, 7, 1)) == date(2026, 7, 29)


def test_open_within_window():
    st, days = status.compute_status(date(2026, 7, 1),
                                     today=date(2026, 7, 10))
    assert st == status.OPEN
    assert days == 19


def test_closing_soon_under_seven_days():
    st, days = status.compute_status(date(2026, 7, 1),
                                     today=date(2026, 7, 24))
    assert st == status.CLOSING_SOON
    assert days == 5


def test_closes_today_is_closing_soon():
    st, days = status.compute_status(date(2026, 7, 1),
                                     today=date(2026, 7, 29))
    assert st == status.CLOSING_SOON
    assert days == 0


def test_closed_after_window():
    st, days = status.compute_status(date(2026, 7, 1),
                                     today=date(2026, 7, 30))
    assert st == status.CLOSED
    assert days == -1


def test_applicant_extended_window_stays_open():
    # applicant kept bidding open: ACD later than certified + 28
    st, days = status.compute_status(date(2026, 7, 1), date(2026, 9, 1),
                                     today=date(2026, 8, 15))
    assert st == status.OPEN
    assert days == 17


def test_unknown_dates_are_closed():
    assert status.compute_status(None, None) == (status.CLOSED, None)


def test_parse_usac_timestamp():
    assert status.parse_usac_date("2026-01-27T13:24:31.000") == date(2026, 1, 27)
    assert status.parse_usac_date(None) is None
    assert status.parse_usac_date("garbage") is None
