"""Fit scoring engine (0-100) with configurable weights.

Subscores are deterministic and explainable; the 2-3 sentence rationale is
AI-written when an Anthropic key is configured (template fallback otherwise).
Weights and strategic preferences live in data/settings.json.
"""
import json
import logging
import math

from . import config, db, status as status_mod

log = logging.getLogger(__name__)

CORE_FUNCTION_HINTS = [
    "internet access", "data transmission", "wireless", "cellular",
    "wi-fi", "wifi", "leased lit fiber", "broadband", "access points",
]


def score_all(rescore: bool = False) -> int:
    """Score every relevant, non-CLOSED RFP. Returns count scored."""
    settings = config.load_settings()
    catalog_terms = _catalog_terms(settings)
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
        breakdown = compute_breakdown(dict(row), days_left, settings,
                                      catalog_terms)
        total = round(sum(b["points"] for b in breakdown.values()), 1)
        rationale = _template_rationale(dict(row), breakdown, total)
        with db.closing_conn() as conn:
            # keep AI-written rationales (they exist iff analysis exists);
            # regenerate template rationales so totals stay in sync
            conn.execute(
                "UPDATE rfps SET fit_score=?, score_breakdown=?, "
                "score_rationale=CASE WHEN analysis IS NOT NULL "
                "THEN COALESCE(score_rationale, ?) ELSE ? END "
                "WHERE application_number=?",
                (total, json.dumps(breakdown), rationale, rationale,
                 row["application_number"]))
            conn.commit()
        scored += 1
    return scored


def _catalog_terms(settings: dict) -> tuple[list, list]:
    """Core/secondary match terms; augmented by uploaded price-list
    categories (price-list categories count as core — we sell them)."""
    core = [t.lower() for t in settings.get("core_services", [])]
    secondary = [t.lower() for t in settings.get("secondary_services", [])]
    with db.closing_conn() as conn:
        cats = conn.execute(
            "SELECT DISTINCT category FROM price_items "
            "WHERE category IS NOT NULL AND category != ''").fetchall()
    core += [c["category"].lower() for c in cats]
    return core, secondary


def compute_breakdown(row: dict, days_left: int | None, settings: dict,
                      catalog_terms: tuple[list, list]) -> dict:
    w = settings["scoring_weights"]
    return {
        "service_match": _service_match(row, w["service_match"], catalog_terms),
        "deal_size": _deal_size(row, w["deal_size"], settings["deal_size"]),
        "winnability": _winnability(row, days_left, w["winnability"]),
        "strategic_fit": _strategic_fit(row, w["strategic_fit"],
                                        settings["strategic_fit"]),
    }


def _service_match(row: dict, max_pts: float,
                   catalog_terms: tuple[list, list]) -> dict:
    core_terms, secondary_terms = catalog_terms
    haystacks = []
    for field in ("service_types", "functions"):
        try:
            haystacks += [s.lower() for s in json.loads(row.get(field) or "[]")]
        except (TypeError, json.JSONDecodeError):
            pass
    for field in ("cat1_description", "cat2_description"):
        if row.get(field):
            haystacks.append(str(row[field]).lower())
    blob = " ; ".join(haystacks)

    core_hits = sorted({t for t in core_terms if t in blob})
    secondary_hits = sorted({t for t in secondary_terms if t in blob})
    if core_hits:
        # any core service = at least 70% of the bucket; more overlap = more
        frac = 0.7 + 0.3 * min(len(core_hits) / 3, 1.0)
    elif secondary_hits:
        frac = 0.35 + 0.15 * min(len(secondary_hits) / 4, 1.0)
    else:
        frac = 0.1  # relevant service_type but nothing matched our catalog
    return {"points": round(max_pts * frac, 1), "max": max_pts,
            "detail": {"core_matches": core_hits,
                       "secondary_matches": secondary_hits}}


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


def _winnability(row: dict, days_left: int | None, max_pts: float) -> dict:
    pts = max_pts
    notes = []
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


def _strategic_fit(row: dict, max_pts: float, cfg: dict) -> dict:
    pts = 0.0
    notes = []
    if row.get("state") in cfg.get("priority_states", []):
        pts += float(cfg.get("priority_state_points", 8))
        notes.append(f"priority state {row.get('state')}")
    etype_pts = cfg.get("entity_type_points", {})
    at = row.get("applicant_type") or ""
    for etype, p in etype_pts.items():
        if etype.lower() in at.lower():
            pts += float(p)
            notes.append(f"entity type: {at}")
            break
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


def _template_rationale(row: dict, breakdown: dict, total: float) -> str:
    """Deterministic fallback rationale; replaced by the AI-written one when
    the analyst pass runs."""
    sm = breakdown["service_match"]["detail"]
    services = ", ".join(sm["core_matches"][:3]) or \
        ", ".join(sm["secondary_matches"][:3]) or "peripheral services"
    spend = row.get("est_prior_spend")
    spend_txt = (f"~${spend:,.0f} est. prior-FY spend" if spend
                 else "no prior-FY spend history found")
    win_notes = breakdown["winnability"]["detail"]["notes"]
    win_txt = win_notes[0] if win_notes else "no major bid barriers identified"
    return (f"{row.get('billed_entity_name', 'Applicant')} ({row.get('state')}) "
            f"requests {services}, with {spend_txt}. "
            f"Winnability check: {win_txt}. Overall fit {total}/100.")
