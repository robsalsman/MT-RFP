"""The LinkedIn Play: makes Kim's Sales Navigator lethal without touching
her account.

LinkedIn has no public API for this and automating a member account
violates LinkedIn's terms (and risks her Navigator subscription), so the
division of labor mirrors how top outbound reps actually work: Matt does
the thinking — who to target at each account, one-click pre-filtered
searches that open in HER logged-in Sales Navigator, and a complete DM
sequence written from the deal's real numbers — and Kim clicks send.

Message doctrine (the "what actually works" school of LinkedIn outbound):
short, human, no pitch in the first touch; value with a real number in
the second; a graceful breakup third. Connect notes under 280 chars.
"""
import logging
import urllib.parse

from . import ai, competitors, savings

log = logging.getLogger(__name__)

# who signs off on connectivity, by entity type
_TITLES = {
    "district": ["Director of Technology", "Chief Technology Officer",
                 "Superintendent", "Assistant Superintendent",
                 "Business Manager"],
    "school": ["Director of Technology", "Principal", "IT Director"],
    "library": ["Library Director", "IT Manager", "Branch Manager",
                "Technology Coordinator"],
    "consortium": ["Executive Director", "Technology Director",
                   "Program Manager"],
}


def _entity_kind(entity_type: str | None) -> str:
    t = (entity_type or "").lower()
    if "librar" in t:
        return "library"
    if "consorti" in t:
        return "consortium"
    if "district" in t:
        return "district"
    return "school"


def _org_short(org: str) -> str:
    """'Newark Indep School District' -> search-friendly short form."""
    s = org.strip()
    for a, b in (("Independent School District", "ISD"),
                 ("Indep School District", "ISD"),
                 ("Indep Sch District", "ISD"),
                 ("Independent Sch Dist", "ISD"),
                 ("School District", "Schools"),
                 ("Public Library System", "Library"),
                 ("Public Library", "Library")):
        if a.lower() in s.lower():
            i = s.lower().index(a.lower())
            s = s[:i] + b + s[i + len(a):]
            break
    return " ".join(s.split())


def search_links(lead: dict) -> list[dict]:
    kind = _entity_kind(lead.get("entity_type"))
    org = _org_short(lead.get("org") or "")
    out = []
    for title in _TITLES[kind][:5]:
        q = f'"{org}" "{title}"'
        enc = urllib.parse.quote(q)
        out.append({
            "title": title,
            "sales_nav_url":
                f"https://www.linkedin.com/sales/search/people?keywords={enc}",
            "linkedin_url": ("https://www.linkedin.com/search/results/"
                             f"people/?keywords={enc}"),
        })
    # the org's company page (posts, staff list, warm-up likes)
    enc_org = urllib.parse.quote(org)
    out.append({
        "title": "Organization page",
        "sales_nav_url": ("https://www.linkedin.com/sales/search/company"
                          f"?keywords={enc_org}"),
        "linkedin_url": ("https://www.linkedin.com/search/results/"
                         f"companies/?keywords={enc_org}"),
    })
    return out


def _facts(lead: dict) -> list[str]:
    sv = savings.compute_savings(lead)
    comp = lead.get("competitor_label") or "their current provider"
    facts = [f"Org: {lead['org']} ({lead['state']})"]
    if sv.get("current_annual"):
        facts.append(f"They pay {comp} ${sv['current_annual']:,.0f}/yr "
                     "(public E-Rate data)")
    if sv.get("ecf_total"):
        facts.append(f"They ran ${sv['ecf_total']:,.0f} of {comp} hotspots "
                     "on ECF funding that has ended")
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
            facts.append(f"{hh:,} households in their zip lost the ACP "
                         "internet subsidy")
    except Exception:
        pass
    return facts


def dm_kit(lead: dict) -> dict:
    """Connect note + 3-touch DM sequence + InMail, from real facts."""
    facts = _facts(lead)
    raw = ai._chat(
        "Write a LinkedIn outreach kit for Kim (Mission Telecom, a "
        "NONPROFIT wireless ISP on the T-Mobile network: hotspot lending "
        "and mobile broadband for schools/libraries, E-Rate eligible, "
        "free CIPA filtering). Style: the high-performing LinkedIn DM "
        "school — short, human, curious, NO pitch in the first touch, "
        "no links in DMs, never salesy. Use ONLY the facts given; numbers "
        "only where specified. Output EXACTLY these five sections, each "
        "starting with the label on its own line:\n"
        "CONNECT NOTE: (under 260 characters, warm, one specific reason "
        "to connect, no pitch)\n"
        "DM 1: (after they accept; 2-3 sentences, one genuine question "
        "about their connectivity program, zero selling)\n"
        "DM 2: (3-4 days later; ONE real number from the facts as a "
        "give — e.g. their public spend or the savings range — and a "
        "soft 15-minute ask)\n"
        "DM 3: (a week later; graceful 2-sentence breakup that leaves "
        "the door open)\n"
        "INMAIL: (subject line then a 90-120 word InMail for when they "
        "don't accept the connect; slightly more complete, still warm)",
        "Facts: " + "; ".join(facts), max_tokens=1400)
    if not raw:
        org = lead["org"]
        raw = (
            "CONNECT NOTE: Hi — I work with schools and libraries on "
            "affordable student connectivity (nonprofit carrier). Given "
            f"your role at {org}, thought it'd be good to be connected. "
            "— Kim\n"
            f"DM 1: Thanks for connecting! Curious — how is {org} "
            "handling home connectivity for students/patrons since the "
            "federal programs wound down? Always interested in what's "
            "working.\n"
            "DM 2: One thing I can share from the public E-Rate data: "
            + (facts[1] + ". " if len(facts) > 1 else "")
            + "As a nonprofit we typically come in well under that — "
            "worth 15 minutes to compare notes?\n"
            "DM 3: Don't want to clutter your inbox — if connectivity "
            "costs ever land on your desk, I'm easy to find. Rooting for "
            "your program either way!\n"
            "INMAIL: Subject: Student connectivity at " + org + "\n"
            "Hi — Kim here from Mission Telecom, a nonprofit wireless "
            "carrier on the T-Mobile network. "
            + (facts[1] + ". " if len(facts) > 1 else "")
            + "Districts like yours typically cut that substantially "
            "with our nonprofit pricing (free CIPA filtering included, "
            "E-Rate eligible). Would a 15-minute call be worth it? — Kim")
    return {"kit": raw.strip(), "facts_used": facts}


def play(lead_id: int) -> dict:
    """The full LinkedIn play for one lead."""
    lead = competitors.get_lead(lead_id)
    if not lead:
        return {"error": "no such lead"}
    kind = _entity_kind(lead.get("entity_type"))
    kit = dm_kit(lead)
    return {
        "org": lead["org"], "state": lead["state"],
        "who_to_target": _TITLES[kind],
        "search_links": search_links(lead),
        **kit,
        "cadence": ("Day 0: connect request (use the note) + like one of "
                    "their org's recent posts. On accept: DM 1. Day +3: "
                    "DM 2. Day +10: DM 3 (breakup). No accept after 5 "
                    "days: InMail. Log each touch with Matt so the "
                    "stale-deal nudges track it."),
        "note": ("Links open pre-filtered searches in Kim's own logged-in "
                 "Sales Navigator/LinkedIn — she sends everything "
                 "herself. Automating a LinkedIn account violates their "
                 "terms, so Matt writes and aims; Kim pulls the trigger."),
    }
