"""The LinkedIn engine: per-person targets, a one-button-per-step cadence,
and a scored queue — LinkedIn as a first-class lead channel.

LinkedIn has no public API and automating a member account violates
their terms (and risks Kim's Sales Navigator subscription), so the split
is: Matt aims (who, exact search link, exact message, exact day) and Kim
pulls the trigger. Every button press advances the funnel: the message is
copied, the search opens in HER logged-in Sales Navigator, the touch is
logged on the lead, and the next step gets a due date.

Cadence (the what-actually-works outbound doctrine): connect note (no
pitch) -> DM 1 on accept (genuine question) -> DM 2 (+3d, one real
number as a give) -> DM 3 (+7d, graceful breakup) -> InMail (fallback
when they never accept).
"""
import datetime
import json
import logging
import re
import urllib.parse

from . import ai, competitors, db, savings

log = logging.getLogger(__name__)

# who signs off on connectivity, by entity type
_TITLES = {
    "district": ["Director of Technology", "Chief Technology Officer",
                 "Superintendent", "Business Manager"],
    "school": ["Director of Technology", "Principal", "IT Director"],
    "library": ["Library Director", "IT Manager",
                "Technology Coordinator"],
    "consortium": ["Executive Director", "Technology Director",
                   "Program Manager"],
}

# step key, label, days after the PREVIOUS step completes
CADENCE = [
    ("connect", "Connect request", 0),
    ("dm1", "DM 1 — after they accept", 1),
    ("dm2", "DM 2 — the give", 3),
    ("dm3", "DM 3 — breakup", 7),
    ("inmail", "InMail — if they never accepted", 0),
]

_SCHEMA = """CREATE TABLE IF NOT EXISTS linkedin_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    person_name TEXT,
    person_title TEXT,
    sales_nav_url TEXT,
    linkedin_url TEXT,
    kit TEXT DEFAULT '{}',
    steps_done TEXT DEFAULT '{}',
    next_step TEXT DEFAULT 'connect',
    next_due TEXT,
    created_at TEXT,
    UNIQUE(lead_id, person_name, person_title)
);"""


def _ensure():
    with db.closing_conn() as conn:
        conn.execute(_SCHEMA)
        conn.commit()


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
    s = org.strip()
    for a, b in (("Independent School District", "ISD"),
                 ("Indep School District", "ISD"),
                 ("Indep Sch District", "ISD"),
                 ("Independent Sch Dist", "ISD"),
                 ("School District", "Schools"),
                 ("School Dist", "Schools"),
                 ("Public Library System", "Library"),
                 ("Public Library", "Library")):
        if a.lower() in s.lower():
            i = s.lower().index(a.lower())
            s = s[:i] + b + s[i + len(a):]
            break
    return " ".join(s.split())


def _search_urls(query: str) -> tuple[str, str]:
    enc = urllib.parse.quote(query)
    return (f"https://www.linkedin.com/sales/search/people?keywords={enc}",
            f"https://www.linkedin.com/search/results/people/?keywords={enc}")


def _name_from_email(email: str) -> str | None:
    """tom.wilkerson@x.org -> 'Tom Wilkerson' (a guess, but searchable)."""
    local = email.split("@")[0]
    parts = re.split(r"[._-]+", local)
    parts = [p for p in parts if p.isalpha() and len(p) > 1]
    if len(parts) >= 2:
        return " ".join(p.capitalize() for p in parts[:3])
    return None


def _known_people(lead: dict) -> list[dict]:
    """Named humans we already have: website-crawl contacts first (they
    have titles), then filing contacts (name or derived from email)."""
    people = []
    seen = set()
    for c in lead.get("extra_contacts", []):
        nm = (c.get("name") or "").strip()
        if nm and nm.lower() not in seen:
            seen.add(nm.lower())
            people.append({"name": nm, "title": c.get("title") or ""})
    for c in lead.get("contacts", []):
        nm, email = competitors._parse_contact(c)
        if not nm and email:
            nm = _name_from_email(email)
        if nm and nm.lower() not in seen:
            seen.add(nm.lower())
            people.append({"name": nm, "title": ""})
    return people[:6]


# ------------------------------------------------------------ the DM kit

_SECTION_RE = re.compile(
    r"(CONNECT NOTE|DM 1|DM 2|DM 3|INMAIL)\s*:?\s*(.*?)(?=(?:CONNECT NOTE|"
    r"DM 1|DM 2|DM 3|INMAIL)\s*:|\Z)", re.DOTALL | re.IGNORECASE)


def _parse_kit(raw: str) -> dict:
    out = {}
    keymap = {"connect note": "connect", "dm 1": "dm1", "dm 2": "dm2",
              "dm 3": "dm3", "inmail": "inmail"}
    for label, body in _SECTION_RE.findall(raw):
        out[keymap[label.lower()]] = body.strip()
    return out


def _facts(lead: dict) -> list[str]:
    sv = savings.compute_savings(lead)
    comp = lead.get("competitor_label") or "their current provider"
    facts = [f"Org: {lead['org']} ({lead['state']})"]
    if sv.get("current_annual"):
        facts.append(f"The org pays {comp} ${sv['current_annual']:,.0f}/yr "
                     "(public E-Rate data)")
    if sv.get("ecf_total"):
        facts.append(f"The org ran ${sv['ecf_total']:,.0f} of {comp} "
                     "hotspots on ECF funding that has ended")
    if sv.get("savings_low") is not None:
        facts.append(f"Savings range ${max(sv['savings_low'],0):,.0f}-"
                     f"${max(sv['savings_high'],0):,.0f}/yr"
                     + (" (estimated)" if sv["estimated"] else ""))
    if lead.get("next_expiration"):
        facts.append(f"Their contract expires {lead['next_expiration']}")
    try:
        from . import acp
        hh = acp.households_for_zip(lead.get("zip"))
        if hh and hh > 200:
            facts.append(f"{hh:,} households in their zip lost the ACP "
                         "internet subsidy")
    except Exception:
        pass
    return facts


def dm_kit(lead: dict, person_name: str | None,
           person_title: str | None) -> dict:
    """Messages FROM Kim TO the prospect, as structured steps."""
    facts = _facts(lead)
    first = (person_name or "").split()[0] if person_name else None
    who = (f"{person_name} ({person_title})" if person_name and person_title
           else person_name or f"the {person_title or 'decision-maker'}"
           f" at {lead['org']}")
    raw = ai._chat(
        "Write LinkedIn messages that KIM (an account executive at Mission "
        "Telecom, a NONPROFIT wireless ISP on the T-Mobile network: "
        "hotspot lending + mobile broadband for schools/libraries, E-Rate "
        f"eligible, free CIPA filtering) will SEND TO {who}. Kim is the "
        "SENDER and signs; the RECIPIENT is the prospect — greet THEM "
        + (f"by first name ({first})" if first else "neutrally (no name)")
        + ", never address Kim. Style: short, human, curious, NO pitch in "
        "the first touch, no links, never salesy. Use ONLY the facts "
        "given. Output EXACTLY five sections, each label on its own "
        "line:\n"
        "CONNECT NOTE: (under 260 characters, one specific genuine reason "
        "to connect, no pitch)\n"
        "DM 1: (2-3 sentences after they accept; one genuine question "
        "about their connectivity program, zero selling)\n"
        "DM 2: (ONE real number from the facts as a give + a soft "
        "15-minute ask)\n"
        "DM 3: (2-sentence graceful breakup, door open)\n"
        "INMAIL: (subject line, then 90-120 words, slightly fuller, warm)",
        "Facts: " + "; ".join(facts), max_tokens=1400)
    kit = _parse_kit(raw) if raw else {}
    if len(kit) < 5:   # offline or malformed -> deterministic templates
        org = lead["org"]
        hi = f"Hi {first}" if first else "Hi"
        give = facts[1] if len(facts) > 1 else \
            "we work with districts like yours on nonprofit pricing"
        kit = {
            "connect": f"{hi} — I work with schools and libraries on "
                       "affordable student connectivity (nonprofit "
                       f"carrier). Given your work at {org}, thought it'd "
                       "be good to be connected. — Kim",
            "dm1": f"Thanks for connecting{', ' + first if first else ''}!"
                   f" Curious — how is {org} handling home connectivity "
                   "for students since the federal programs wound down? "
                   "Always interested in what's working.",
            "dm2": f"One thing I can share from the public data: {give}. "
                   "As a nonprofit we typically come in well under that — "
                   "worth 15 minutes to compare notes?",
            "dm3": "Don't want to clutter your inbox — if connectivity "
                   "costs ever land on your desk, I'm easy to find. "
                   "Rooting for your program either way! — Kim",
            "inmail": f"Subject: Student connectivity at {org}\n\n{hi} — "
                      "Kim here from Mission Telecom, a nonprofit "
                      "wireless carrier on the T-Mobile network. "
                      f"{give}. Districts like yours typically cut that "
                      "substantially with our nonprofit pricing (free "
                      "CIPA filtering, E-Rate eligible). Would a "
                      "15-minute call be worth it? — Kim",
        }
    return kit


# ------------------------------------------------------- targets & queue

def build_targets(lead_id: int) -> dict:
    """Create queue targets for a lead: every KNOWN contact by name, plus
    title-based searches for the org's decision-makers."""
    _ensure()
    lead = competitors.get_lead(lead_id)
    if not lead:
        return {"error": "no such lead"}
    org = _org_short(lead["org"])
    kind = _entity_kind(lead.get("entity_type"))
    now = datetime.datetime.utcnow().isoformat(timespec="seconds")
    targets = []
    for p in _known_people(lead):
        nav, li = _search_urls(f'"{p["name"]}" "{org}"'
                               if org.lower() not in p["name"].lower()
                               else f'"{p["name"]}"')
        targets.append({"person_name": p["name"],
                        "person_title": p.get("title") or "known contact",
                        "nav": nav, "li": li})
    for title in _TITLES[kind][:3]:
        nav, li = _search_urls(f'"{org}" "{title}"')
        targets.append({"person_name": None, "person_title": title,
                        "nav": nav, "li": li})
    created = 0
    with db.closing_conn() as conn:
        for t in targets:
            kit = dm_kit(lead, t["person_name"], t["person_title"])
            cur = conn.execute(
                """INSERT INTO linkedin_targets
                   (lead_id, person_name, person_title, sales_nav_url,
                    linkedin_url, kit, next_step, next_due, created_at)
                   VALUES (?,?,?,?,?,?,'connect',?,?)
                   ON CONFLICT(lead_id, person_name, person_title)
                   DO NOTHING""",
                (lead_id, t["person_name"], t["person_title"], t["nav"],
                 t["li"], json.dumps(kit), now[:10], now))
            created += cur.rowcount
        conn.commit()
    return {"lead_id": lead_id, "org": lead["org"],
            "targets_created": created,
            "targets_total": len(targets)}


def mark_step(target_id: int, step: str) -> dict:
    """Kim did a step. Log it, schedule the next one — the funnel moves."""
    _ensure()
    keys = [k for k, _, _ in CADENCE]
    if step not in keys:
        return {"error": f"unknown step '{step}'"}
    now = datetime.datetime.utcnow()
    with db.closing_conn() as conn:
        row = conn.execute("SELECT * FROM linkedin_targets WHERE id=?",
                           (target_id,)).fetchone()
        if not row:
            return {"error": "no such target"}
        t = dict(row)
        done = json.loads(t["steps_done"] or "{}")
        done[step] = now.isoformat(timespec="seconds")
        idx = keys.index(step)
        if idx + 1 < len(keys):
            nxt_key, _, offset = CADENCE[idx + 1]
            due = (now + datetime.timedelta(days=offset)).date().isoformat()
        else:
            nxt_key, due = "done", None
        conn.execute(
            "UPDATE linkedin_targets SET steps_done=?, next_step=?, "
            "next_due=? WHERE id=?",
            (json.dumps(done), nxt_key, due, target_id))
        conn.commit()
    who = t["person_name"] or t["person_title"]
    label = dict((k, lb) for k, lb, _ in CADENCE)[step]
    competitors.add_note(t["lead_id"], f"LinkedIn: {label} -> {who}")
    # first touch on a fresh lead moves it into the pipeline
    lead = competitors.get_lead(t["lead_id"])
    if lead and lead.get("status") == "new":
        competitors.set_status(t["lead_id"], "contacted")
    return {"ok": True, "next_step": nxt_key, "next_due": due,
            "logged_on_lead": t["lead_id"]}


def queue(limit: int = 30, due_only: bool = False) -> dict:
    """The scored contact queue: who to touch today, best deals first."""
    _ensure()
    today = datetime.date.today().isoformat()
    with db.closing_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            """SELECT t.*, c.org, c.state, c.spend, c.source, c.devices,
                      c.next_expiration, c.competitor,
                      c.status AS lead_status
               FROM linkedin_targets t
               JOIN competitor_leads c ON c.id = t.lead_id
               WHERE t.next_step != 'done'
                 AND c.status NOT IN ('dismissed','lost','won')
               ORDER BY t.next_due ASC, c.spend DESC
               LIMIT ?""", (max(limit * 3, 60),))]
    out = []
    for t in rows:
        due = t["next_due"] or today
        if due_only and due > today:
            continue
        score = float(t["spend"] or 0)
        if t.get("source") == "ecf":
            score *= 0.6      # program total, not annual — damp it
        if t.get("next_expiration") and today <= t["next_expiration"] \
                <= (datetime.date.today()
                    + datetime.timedelta(days=456)).isoformat():
            score *= 1.5      # renewal window opening
        kit = json.loads(t["kit"] or "{}")
        label = dict((k, lb) for k, lb, _ in CADENCE)
        out.append({
            "target_id": t["id"], "lead_id": t["lead_id"],
            "person": t["person_name"] or f"({t['person_title']})",
            "title": t["person_title"], "org": t["org"],
            "state": t["state"],
            "competitor": competitors.COMPETITORS.get(
                t["competitor"], {}).get("label", t["competitor"]),
            "spend": t["spend"], "source": t["source"],
            "expires": t["next_expiration"],
            "lead_stage": t["lead_status"], "score": round(score),
            "next_step": t["next_step"],
            "next_step_label": label.get(t["next_step"], t["next_step"]),
            "due": due, "due_now": due <= today,
            "message": kit.get(t["next_step"], ""),
            "sales_nav_url": t["sales_nav_url"],
            "linkedin_url": t["linkedin_url"],
            "steps_done": json.loads(t["steps_done"] or "{}"),
        })
    out.sort(key=lambda x: (not x["due_now"], -x["score"]))
    return {"count": len(out[:limit]), "targets": out[:limit],
            "cadence": [{"key": k, "label": lb, "days_after_prev": d}
                        for k, lb, d in CADENCE]}


def build_top(n: int = 8) -> dict:
    """Seed the queue from the best untouched board leads."""
    _ensure()
    with db.closing_conn() as conn:
        ids = [r[0] for r in conn.execute(
            """SELECT id FROM competitor_leads
               WHERE status NOT IN ('dismissed','lost','won')
                 AND id NOT IN (SELECT DISTINCT lead_id
                                FROM linkedin_targets)
               ORDER BY spend DESC LIMIT ?""", (max(1, min(n, 20)),))]
    built = 0
    for lid in ids:
        r = build_targets(lid)
        built += r.get("targets_created", 0)
    return {"leads_processed": len(ids), "targets_created": built}


def play(lead_id: int) -> dict:
    """Chat-facing: ensure targets exist, return the queue slice for this
    lead."""
    r = build_targets(lead_id)
    if r.get("error"):
        return r
    q = queue(50)
    mine = [t for t in q["targets"] if t["lead_id"] == lead_id]
    return {"org": r["org"], "targets": mine,
            "note": ("Targets are in the LinkedIn tab queue. Each button "
                     "opens the search in Kim's own Sales Navigator and "
                     "copies the message — she sends it herself (account "
                     "automation violates LinkedIn's terms)."),
            "how": "navigate tab=linkedin to work the queue"}
