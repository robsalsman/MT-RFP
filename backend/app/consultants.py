"""The consultant channel: E-Rate consultants file for dozens-to-hundreds
of districts each, and we already capture them on every lead and RFP. One
warm consultant relationship = every client of theirs hearing about
Mission Telecom's nonprofit pricing at once.

Everything here is aggregated from data already in the local DB — no new
external calls.
"""
import json
import logging
import re

from . import ai, db

log = logging.getLogger(__name__)


def _norm(name: str) -> str:
    """Consultant names vary by case/punctuation across filings."""
    n = re.sub(r"[^A-Z0-9 ]+", " ", (name or "").upper())
    n = re.sub(r"\b(INC|LLC|LLP|LTD|CO|CORP|COMPANY|CONSULTING|CONSULTANTS|"
               r"GROUP|SERVICES)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def board(limit: int = 25) -> list[dict]:
    """Rank consultants by reach across the competitor board + RFP feed."""
    agg: dict[str, dict] = {}

    def add(display: str, email: str | None, org: str, state: str,
            spend: float, kind: str):
        key = _norm(display)
        if not key:
            return
        c = agg.setdefault(key, {
            "name": display.strip(), "emails": set(), "clients": {},
            "states": set(), "competitor_spend": 0.0, "rfp_clients": 0})
        if email:
            c["emails"].add(email.lower())
        if org:
            c["clients"][org] = max(c["clients"].get(org, 0), spend or 0)
        if state:
            c["states"].add(state)
        if kind == "lead":
            c["competitor_spend"] += spend or 0
        else:
            c["rfp_clients"] += 1

    with db.closing_conn() as conn:
        for r in conn.execute(
                "SELECT consultants, org, state, spend FROM competitor_leads "
                "WHERE status != 'dismissed'"):
            for x in json.loads(r["consultants"] or "[]"):
                m = re.match(r"^(.*?)\s*<([^>]+)>$", x)
                name, email = (m.group(1), m.group(2)) if m else (x, None)
                add(name, email, r["org"], r["state"], r["spend"], "lead")

    out = []
    for c in agg.values():
        clients = sorted(c["clients"].items(), key=lambda kv: -kv[1])
        out.append({
            "name": c["name"],
            "emails": sorted(c["emails"])[:3],
            "client_count": len(c["clients"]),
            "states": sorted(c["states"]),
            "competitor_spend": round(c["competitor_spend"], 2),
            "top_clients": [{"org": o, "spend": round(s, 2)}
                            for o, s in clients[:8]],
        })
    out.sort(key=lambda c: (c["client_count"], c["competitor_spend"]),
             reverse=True)
    return out[:max(1, min(int(limit or 25), 100))]


def draft_partner_pitch(consultant_name: str) -> dict:
    """Draft Kim's partnership email to a consultant, from real numbers."""
    target = None
    for c in board(100):
        if _norm(c["name"]) == _norm(consultant_name) \
                or _norm(consultant_name) in _norm(c["name"]):
            target = c
            break
    if not target:
        return {"error": f"no consultant matching '{consultant_name}' on "
                         "the board"}
    facts = [
        f"Consultant: {target['name']}",
        f"They represent {target['client_count']} schools/libraries on our "
        f"board (states: {', '.join(target['states'][:8])}) whose mobile-"
        f"broadband spend with competitors totals "
        f"${target['competitor_spend']:,.0f}.",
        "Sample clients: " + "; ".join(
            f"{t['org']} (${t['spend']:,.0f})"
            for t in target["top_clients"][:4]),
    ]
    raw = ai._chat(
        "You write short partnership emails for Kim, an account executive "
        "at Mission Telecom — a NONPROFIT wireless ISP on the T-Mobile "
        "network (LTE/5G broadband + hotspot lending for schools and "
        "libraries, E-Rate eligible, from $20-25/line/month, free CIPA "
        "filtering). Audience: an E-RATE CONSULTANT who advises many "
        "districts. Angle: partnering makes THEM look good — nonprofit "
        "pricing saves their clients money and Mission handles E-Rate "
        "paperwork cleanly; this is a value-add for their whole client "
        "base, not a vendor pitch for one deal. Under 170 words, plain "
        "text, subject line first, cite the real numbers given, end with "
        "a 15-minute call ask, sign Kim, Mission Telecom. Use ONLY the "
        "facts provided.",
        "Facts:\n- " + "\n- ".join(facts), max_tokens=1200)
    if not raw:
        return {"error": "draft generation failed — try again"}
    return {"draft": raw.strip(),
            "to": target["emails"][0] if target["emails"] else None,
            "consultant": target["name"],
            "client_count": target["client_count"]}
