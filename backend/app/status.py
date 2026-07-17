"""Bid-window status math. Pure functions — unit tested.

A Form 470 is open for bidding from its certified date until at least
certified + 28 days (the "allowable contract date", ACD). USAC supplies the
ACD; when absent we compute certified + 28 days. Applicants may keep bidding
open longer, but the ACD is the earliest close we can guarantee, so status is
computed against it dynamically on every read — no funding year is hardcoded.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import config

EASTERN = ZoneInfo(config.EASTERN_TZ)

OPEN = "OPEN"
CLOSING_SOON = "CLOSING SOON"
CLOSED = "CLOSED"


def parse_usac_date(value: str | None) -> date | None:
    """USAC floating timestamps like '2026-07-01T13:24:31.000' -> date."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "")).date()
    except ValueError:
        return None


def allowable_contract_date(certified: date | None,
                            acd: date | None = None) -> date | None:
    """USAC's ACD when present, else certified + 28 days."""
    if acd:
        return acd
    if certified:
        return certified + timedelta(days=config.BID_WINDOW_DAYS)
    return None


def today_eastern() -> date:
    return datetime.now(tz=EASTERN).date()


def compute_status(certified: date | None, acd: date | None = None,
                   today: date | None = None) -> tuple[str, int | None]:
    """Returns (status, days_left). days_left is days until the ACD
    (0 = closes today); None when dates are unknown."""
    today = today or today_eastern()
    close = allowable_contract_date(certified, acd)
    if close is None:
        return CLOSED, None
    days_left = (close - today).days
    if days_left < 0:
        return CLOSED, days_left
    if days_left < config.CLOSING_SOON_DAYS:
        return CLOSING_SOON, days_left
    return OPEN, days_left
