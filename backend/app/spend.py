"""Estimate an applicant's annual connectivity spend from prior-year Form 471
filings (FRN Status dataset), keyed on Billed Entity Number.

Dollar amounts never appear on a Form 470; the best available deal-size proxy
is what the same BEN requested/was committed in the most recent funding year
with data. We sum total_pre_discount_costs (the full vendor-billed amount,
before the E-Rate discount) across the BEN's FRNs.
"""
import logging

from . import config, soda

log = logging.getLogger(__name__)

BATCH = 100


def prior_spend_by_ben(bens: list[str], current_fy: int) -> dict[str, dict]:
    """For each BEN return {'spend': float, 'funding_year': int} from the most
    recent of the two prior funding years that has data."""
    result: dict[str, dict] = {}
    remaining = sorted({b for b in bens if b})
    for fy in (current_fy - 1, current_fy - 2):
        if not remaining:
            break
        found = _spend_for_year(remaining, fy)
        for ben, spend in found.items():
            result[ben] = {"spend": spend, "funding_year": fy}
        remaining = [b for b in remaining if b not in found]
    return result


def _spend_for_year(bens: list[str], fy: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for i in range(0, len(bens), BATCH):
        chunk = bens[i:i + BATCH]
        ben_list = ",".join(f"'{b}'" for b in chunk)
        where = f"funding_year='{fy}' AND ben in({ben_list})"
        try:
            rows = soda.fetch_all(
                config.DATASET_FRN_STATUS, where=where,
                select="ben, sum(total_pre_discount_costs) as spend",
                group="ben", order="ben")
        except Exception as e:
            log.warning("prior-spend query failed (FY%s): %s", fy, e)
            continue
        for r in rows:
            try:
                spend = float(r.get("spend") or 0)
            except (TypeError, ValueError):
                continue
            if spend > 0:
                out[r["ben"]] = round(spend, 2)
    return out
