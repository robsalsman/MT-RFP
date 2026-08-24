"""Conversational deal-closers: objection handling, follow-up nudges, and
same-hour call recaps. AI-written when the cloud is up; deterministic
templates otherwise — Kim always gets something sendable.
"""
import logging
import re

from . import ai, competitors, savings

log = logging.getLogger(__name__)

# objection classes and the honest counter-angle for each
OBJECTIONS = {
    "price": ("they think it's expensive or budget is tight",
              "nonprofit pricing beats their current per-line cost; cite "
              "their real spend and the savings range"),
    "under_contract": ("they're locked in with the incumbent",
                       "renewal timing: we quote now, they compare at "
                       "expiration; E-Rate requires competitive bids "
                       "anyway"),
    "coverage": ("they doubt wireless/T-Mobile coverage",
                 "offer a free pilot unit test at their sites — data "
                 "beats debate"),
    "satisfied": ("happy with the incumbent",
                  "great position — a free benchmark quote costs nothing "
                  "and strengthens their next negotiation"),
    "no_need": ("they say students/patrons are covered",
                "ACP ended — cite households in their zip that lost the "
                "subsidy"),
    "procurement": ("process/RFP/board hurdles",
                    "we support the Form 470 process end-to-end and can "
                    "provide board-ready materials"),
    "timing": ("not now / next year",
               "E-Rate calendar: acting this cycle means funded service "
               "next July; waiting costs a full year"),
}


def _classify(reply_text: str) -> str:
    t = reply_text.lower()
    rules = [
        ("price", ("expensive", "cost", "budget", "afford", "cheaper",
                   "price")),
        ("under_contract", ("contract", "locked", "term", "agreement",
                            "renew")),
        ("coverage", ("coverage", "signal", "rural", "dead zone",
                      "t-mobile", "reception")),
        ("satisfied", ("happy", "satisfied", "works fine", "no complaints",
                       "good with")),
        ("no_need", ("don't need", "no need", "covered", "already have")),
        ("procurement", ("rfp", "bid", "board", "procurement", "process",
                         "470", "purchasing")),
        ("timing", ("next year", "not now", "later", "budget cycle",
                    "revisit", "busy")),
    ]
    for key, words in rules:
        if any(w in t for w in words):
            return key
    return "timing"


def handle_objection(lead_id: int | None, reply_text: str) -> dict:
    lead = competitors.get_lead(lead_id) if lead_id else None
    kind = _classify(reply_text)
    desc, angle = OBJECTIONS[kind]
    facts = []
    if lead:
        sv = savings.compute_savings(lead)
        comp = lead.get("competitor_label") or "their provider"
        if sv.get("current_annual"):
            facts.append(f"They pay {comp} ${sv['current_annual']:,.0f}/yr")
        if sv.get("savings_low") is not None:
            facts.append(f"Savings range ${max(sv['savings_low'],0):,.0f}-"
                         f"${max(sv['savings_high'],0):,.0f}/yr"
                         + (" (estimated)" if sv["estimated"] else ""))
        if lead.get("next_expiration"):
            facts.append(f"Contract expires {lead['next_expiration']}")
        try:
            from . import acp
            hh = acp.households_for_zip(lead.get("zip"))
            if hh and hh > 200:
                facts.append(f"{hh:,} households in their zip lost ACP")
        except Exception:
            pass
        competitors.add_note(lead_id, f"Objection ({kind}): "
                             + reply_text[:300])
    cal = savings.erate_sign_by()
    facts.append(f"E-Rate: acting this cycle = funded service July "
                 f"{cal['next_funding_year']}")
    raw = ai._chat(
        "You help Kim (Mission Telecom, nonprofit mobile carrier on "
        "T-Mobile — hotspots and cell phones) answer a prospect's objection. Write a short reply "
        "email (under 130 words, plain text, no subject) that "
        f"acknowledges their point gracefully, then uses this angle: "
        f"{angle}. Use ONLY the facts given; never invent numbers. End "
        "with one low-pressure specific ask. Sign as Kim.",
        f"Their reply: {reply_text[:600]}\n\nFacts: " + "; ".join(facts),
        max_tokens=900)
    if not raw:
        raw = (f"Thanks for the candid reply — completely fair. "
               f"One thought: {angle}. "
               + (facts[0] + ". " if facts else "")
               + "Would a 15-minute call be worth it to pressure-test the "
                 "numbers? — Kim")
    return {"objection_type": kind, "objection_meaning": desc,
            "counter_angle": angle, "draft_reply": raw.strip(),
            "facts_used": facts}


def draft_followup(lead_id: int) -> dict:
    lead = competitors.get_lead(lead_id)
    if not lead:
        return {"error": "no such lead"}
    stage = lead.get("status") or "contacted"
    sv = savings.compute_savings(lead)
    comp = lead.get("competitor_label") or "their provider"
    facts = [f"Org: {lead['org']} ({lead['state']})", f"Stage: {stage}"]
    if sv.get("current_annual"):
        facts.append(f"They pay {comp} ${sv['current_annual']:,.0f}/yr")
    if sv.get("savings_low") is not None:
        facts.append(f"Savings ${max(sv['savings_low'],0):,.0f}-"
                     f"${max(sv['savings_high'],0):,.0f}/yr"
                     + (" est." if sv["estimated"] else ""))
    notes = lead.get("notes") or []
    if notes:
        facts.append("Last note: " + notes[-1].get("text", "")[:200])
    try:
        from . import vault
        memory = vault.lead_context(lead, max_chars=600)
        if memory:
            facts.append("Account memory: " + memory)
    except Exception:
        pass
    angle = {"contacted": "gentle second touch, one new fact, easy out",
             "replied": "keep momentum, propose two specific times",
             "meeting": "confirm the meeting and preview the one number "
                        "they'll care about",
             "quote": "the quote is sitting — offer to walk it through in "
                      "10 minutes, mention the E-Rate clock",
             "verbal": "verbal yes but unsigned — make signing trivial, "
                       "restate the deadline"}.get(stage, "warm check-in")
    raw = ai._chat(
        "Write Kim's follow-up email (under 110 words, plain text, "
        "subject line first). Mission Telecom, nonprofit mobile carrier "
        f"(hotspots + cell phones) on T-Mobile. Angle for this touch: {angle}. Use ONLY the facts "
        "given. Friendly, zero pressure, one specific ask. Sign as Kim.",
        "Facts: " + "; ".join(facts), max_tokens=800)
    if not raw:
        raw = (f"Subject: Quick nudge — {lead['org']}\n\nHi there,\n\n"
               "Circling back on my last note. "
               + (f"The numbers still stand ({facts[2]}). " if len(facts) > 2
                  else "")
               + "Worth 10 minutes this week?\n\nKim\nMission Telecom")
    return {"stage": stage, "draft": raw.strip(), "org": lead["org"]}


def log_debrief(lead_id: int, debrief: str) -> dict:
    """Store Kim's call debrief, extract commitments, draft the recap."""
    lead = competitors.get_lead(lead_id)
    if not lead:
        return {"error": "no such lead"}
    competitors.add_note(lead_id, "Call debrief: " + debrief[:1500])
    raw = ai._chat(
        "From Kim's rough call debrief, produce: (1) line 'NEXT STEPS:' "
        "then up to 4 short bullet lines of commitments/actions with "
        "owners, (2) a blank line, (3) 'RECAP EMAIL:' then a short "
        "same-day recap email to the prospect (under 120 words, subject "
        "first, thanks them, lists what was agreed, confirms the next "
        "step + date, signs Kim, Mission Telecom). Plain text only. Use "
        "ONLY what the debrief says.",
        f"Prospect: {lead['org']}\nDebrief: {debrief[:1200]}",
        max_tokens=1000)
    if not raw:
        raw = ("NEXT STEPS:\n- [from your debrief — cloud drafting is "
               "offline]\n\nRECAP EMAIL:\nSubject: Great speaking today — "
               f"{lead['org']}\n\nThanks for the time today. As discussed: "
               + debrief[:200] + "\n\nI'll follow up as agreed.\n\nKim\n"
               "Mission Telecom")
    return {"org": lead["org"], "logged": True, "output": raw.strip()}
