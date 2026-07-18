"""Fit scoring engine (0-100), tuned to Mission Telecom's real business.

Mission Telecom is a nonprofit wireless ISP on the T-Mobile network (see
app/mission_fit.py and config.MISSION_TELECOM). Scoring finds the E-Rate RFPs
it can actually bid on and win — Category 1 internet access / data
transmission deliverable over fixed wireless / cellular, especially for
libraries and schools — and pushes down the ones it can't serve (dedicated
fiber, multi-gig circuits, Category 2 LAN hardware).

Subscores are deterministic and explainable; the rationale is AI-written when
a provider key is set (template fallback otherwise). Weights live in
data/settings.json.
"""
import json
import logging
import math

from . import config, db, mission_fit, status as status_mod

log = logging.getLogger(__name__)

# When Mission Telecom can't deliver the requested service, the rubric total
# is scaled down hard so non-fits sink below every real opportunity.
NONBIDDABLE_FACTOR = 0.3


def score_all(rescore: bool = False) -> int:
    """Score every relevant, non-CLOSED RFP. Returns count scored."""
    settings = config.load_settings()
    with db.closing_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM rfps WHERE relevant=1").fetchall()
    scored = 0
    for row in rows:
        st, days_left = status_mod.compute_status(
            status_mod.parse_usac_date(row["certified_date"]),
            status_mod.parse_usac_date(row["allowable_contract_date"]))
        if st == status_mod.CLOSED:
            continue
        if row["fit_score"] is not None and not rescore:
            continue
        with db.closing_conn() as conn:
            srs = [dict(r) for r in conn.execute(
                "SELECT * FROM service_requests WHERE application_number=?",
                (row["application_number"],)).fetchall()]
        fit = mission_fit.assess(dict(row), srs)
        breakdown = compute_breakdown(dict(row), fit, days_left, settings)
        total = round(sum(b["points"] for b in breakdown.values()), 1)
        if not fit["biddable"]:
            total = round(total * NONBIDDABLE_FACTOR, 1)
        rationale = _template_rationale(dict(row), breakdown, fit, total)
        with db.closing_conn() as conn:
            # keep AI-written rationales (they exist iff analysis exists);
            # regenerate template rationales so totals stay in sync
            conn.execute(
                "UPDATE rfps SET fit_score=?, score_breakdown=?, "
                "mission_biddable=?, mission_blockers=?, "
                "score_rationale=CASE WHEN analysis IS NOT NULL "
                "THEN COALESCE(score_rationale, ?) ELSE ? END "
                "WHERE application_number=?",
                (total, json.dumps(breakdown),
                 1 if fit["biddable"] else 0, json.dumps(fit["blockers"]),
                 rationale, rationale, row["application_number"]))
            conn.commit()
        scored += 1
    return scored


def compute_breakdown(row: dict, fit: dict, days_left: int | None,
                      settings: dict) -> dict:
    w = settings["scoring_weights"]
    return {
        "service_match": _service_match(fit, w["service_match"]),
        "deal_size": _deal_size(row, w["deal_size"], settings["deal_size"]),
        "winnability": _winnability(row, fit, days_left, w["winnability"]),
        "strategic_fit": _strategic_fit(row, fit, w["strategic_fit"],
                                        settings["strategic_fit"]),
    }


def _service_match(fit: dict, max_pts: float) -> dict:
    """How well the RFP matches Mission Telecom's wireless-connectivity
    catalog (mission_fit.assess computes the fraction)."""
    return {"points": round(max_pts * fit["service_fraction"], 1),
            "max": max_pts,
            "detail": {"mission_matches": fit["matched"],
                       "wireless_signal": fit["wireless_signal"],
                       "biddable": fit["biddable"],
                       "max_mbps": fit["max_mbps"],
                       "blockers": fit["blockers"],
                       "concerns": fit.get("concerns", [])}}


def _deal_size(row: dict, max_pts: float, cfg: dict) -> dict:
    spend = row.get("est_prior_spend")
    floor = float(cfg.get("floor_points", 5))
    full_at = float(cfg.get("full_points_at_annual_spend", 250000))
    if not spend or spend <= 0:
        return {"points": floor, "max": max_pts,
                "detail": {"note": "no prior-FY 471 spend found; floor applied"}}
    # log scale: $1k -> near floor, full_at -> max
    frac = min(math.log10(max(spend, 1000) / 1000) /
               math.log10(full_at / 1000), 1.0)
    pts = max(floor, round(floor + (max_pts - floor) * frac, 1))
    return {"points": pts, "max": max_pts,
            "detail": {"est_prior_spend": spend}}


def _winnability(row: dict, fit: dict, days_left: int | None,
                 max_pts: float) -> dict:
    pts = max_pts
    notes = []
    if not fit["biddable"]:
        notes.append("Mission Telecom cannot deliver the requested service")
    if row.get("state_or_local_restrictions"):
        pts -= max_pts * 0.35
        notes.append("state/local procurement restrictions apply")
    if days_left is not None:
        if days_left < 7:
            pts -= max_pts * 0.3
            notes.append(f"only {days_left} day(s) left in bid window")
        elif days_left < 14:
            pts -= max_pts * 0.15
            notes.append(f"{days_left} days left in bid window")
    if not row.get("has_rfp_docs"):
        notes.append("no formal RFP attached (470-only; lighter-weight bid)")
    analysis = _parse_analysis(row)
    if analysis:
        barriers = analysis.get("mandatory_requirements") or []
        if len(barriers) > 6:
            pts -= max_pts * 0.15
            notes.append(f"{len(barriers)} mandatory requirements")
        if analysis.get("price_primary_factor"):
            notes.append("RFP confirms price as primary evaluation factor")
        for d in analysis.get("disqualifiers") or []:
            pts -= max_pts * 0.2
            notes.append(f"potential disqualifier: {d}")
    return {"points": round(max(pts, 0), 1), "max": max_pts,
            "detail": {"notes": notes}}


def _strategic_fit(row: dict, fit: dict, max_pts: float, cfg: dict) -> dict:
    pts = 0.0
    notes = []
    if row.get("state") in cfg.get("priority_states", []):
        pts += float(cfg.get("priority_state_points", 8))
        notes.append(f"priority state {row.get('state')}")
    etype_pts = cfg.get("entity_type_points", {})
    at = row.get("applicant_type") or ""
    # longest matching entity label wins (so "Library System" beats "Library")
    best = max((e for e in etype_pts if e.lower() in at.lower()),
               key=len, default=None)
    if best:
        pts += float(etype_pts[best])
        notes.append(f"entity type: {at}")
    if fit.get("wireless_signal"):
        pts += 3
        notes.append("RFP explicitly seeks wireless connectivity")
    analysis = _parse_analysis(row)
    term = (analysis or {}).get("contract_term_years")
    if term:
        try:
            if float(term) >= float(cfg.get("preferred_contract_years_min", 3)):
                pts += float(cfg.get("multi_year_points", 6))
                notes.append(f"multi-year term ({term}y)")
        except (TypeError, ValueError):
            pass
    return {"points": round(min(pts, max_pts), 1), "max": max_pts,
            "detail": {"notes": notes}}


def _parse_analysis(row: dict) -> dict | None:
    try:
        return json.loads(row.get("analysis") or "null")
    except (TypeError, json.JSONDecodeError):
        return None


def _template_rationale(row: dict, breakdown: dict, fit: dict,
                        total: float) -> str:
    """Deterministic fallback rationale; replaced by the AI-written one when
    the analyst pass runs."""
    entity = row.get("billed_entity_name", "Applicant")
    state = row.get("state")
    spend = row.get("est_prior_spend")
    spend_txt = (f"~${spend:,.0f} est. prior-FY spend" if spend
                 else "no prior-FY spend history found")
    if not fit["biddable"]:
        why = fit["blockers"][0] if fit["blockers"] else \
            "outside Mission Telecom's wireless service scope"
        return (f"{entity} ({state}) — NOT a Mission Telecom fit: {why}. "
                f"Scored {total}/100 ({spend_txt}).")
    services = ", ".join(fit["matched"][:3]) or \
        "internet access / data transmission"
    extra = (" RFP explicitly wants wireless — a direct match for Mission "
             "Telecom's fixed-wireless/cellular service." if
             fit["wireless_signal"] else "")
    win_notes = breakdown["winnability"]["detail"]["notes"]
    win_txt = win_notes[0] if win_notes else "no major bid barriers identified"
    return (f"{entity} ({state}) requests {services}, deliverable over Mission "
            f"Telecom's wireless network; {spend_txt}.{extra} "
            f"Winnability: {win_txt}. Overall fit {total}/100.")
