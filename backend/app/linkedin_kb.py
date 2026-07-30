"""Matt's Sales Navigator expertise: the complete playbook, curated.

Everything the "outbound that actually works" school teaches, plus
Navigator's real features, deep links, and safety limits — so Kim never
has to learn the tool. Matt answers any LinkedIn question from this KB,
hands her the exact link into the right LinkedIn screen, and gives her
paste-ready content. Her job is clicking.

Every topic: know (expert facts Matt answers from), links (label, URL
deep into LinkedIn), do (the click-by-click, written for zero prior
knowledge).
"""
import urllib.parse

KB = {
    "getting_around": {
        "title": "Getting around Sales Navigator",
        "know": [
            "Sales Navigator is a separate app from normal LinkedIn — "
            "same login, different screens. The home feed shows alerts "
            "about your saved leads (job changes, posts, funding news).",
            "The three things that matter: People search, Lead Lists, "
            "and the Inbox (InMail). Everything else is gravy.",
            "Anything Kim does in Navigator (viewing, searching, saving) "
            "is invisible to prospects except profile views — and view "
            "privacy can be set to private mode.",
        ],
        "links": [
            ("Sales Navigator home (your alert feed)",
             "https://www.linkedin.com/sales/home"),
            ("People search", "https://www.linkedin.com/sales/search/people"),
            ("Your lead lists", "https://www.linkedin.com/sales/lists/people"),
            ("Navigator inbox / InMail",
             "https://www.linkedin.com/sales/inbox"),
        ],
        "do": "Bookmark the home link. Check it each morning right after "
              "the RFP Rockstar LinkedIn tab — your saved leads' news is "
              "conversation fuel.",
    },
    "boolean_search": {
        "title": "Boolean search — finding exactly the right person",
        "know": [
            'Quotes lock a phrase: "Director of Technology" only matches '
            "that exact title.",
            "OR widens: \"Director of Technology\" OR CTO OR "
            '"Technology Coordinator". AND narrows. NOT excludes: '
            "NOT retired.",
            "Search the ORG NAME in quotes plus the title — that's how "
            "RFP Rockstar's one-click links are built.",
            "After a keyword search, use the left-side filters to tighten: "
            "Geography (their state), Current company, Seniority. Filters "
            "beat more keywords.",
        ],
        "links": [
            ("People search (paste boolean here)",
             "https://www.linkedin.com/sales/search/people"),
        ],
        "do": "You rarely need to type these — the LinkedIn tab's ▶ "
              "buttons carry the boolean pre-built. Ask Matt 'build me a "
              "search for ___' for anything custom.",
    },
    "saved_searches": {
        "title": "Saved searches — prospecting on autopilot",
        "know": [
            "Any search can be SAVED; Navigator then emails/alerts when "
            "NEW people match it — new tech director hired in a target "
            "district = automatic warm timing (new leaders change vendors "
            "in their first year).",
            "The money search to save: your states + titles (Director of "
            "Technology OR CTO OR Superintendent) + K-12/library keywords. "
            "New matches = people to add to the queue.",
        ],
        "links": [
            ("Run a search, then click 'Save search' (top right of "
             "results)", "https://www.linkedin.com/sales/search/people"),
            ("Your saved searches",
             "https://www.linkedin.com/sales/saved-searches/people"),
        ],
        "do": "Click the first link, run one search Matt builds for you, "
              "hit 'Save search' top-right, set alerts to Weekly. Done — "
              "Navigator now prospects while you sleep.",
    },
    "lead_lists": {
        "title": "Lead lists — your Navigator mirror of the deal board",
        "know": [
            "Saving someone as a Lead puts them on a list and turns on "
            "alerts about them (job changes, posts) in your home feed.",
            "Best practice: one list per campaign — e.g. 'Kajeet "
            "win-backs', 'Expiring contracts 2026'. Mirrors the RFP "
            "Rockstar board stages.",
            "When a saved lead POSTS something, comment before you DM — "
            "a comment-then-message shows up warm, not cold.",
        ],
        "links": [
            ("Your lead lists",
             "https://www.linkedin.com/sales/lists/people"),
        ],
        "do": "When you find the right person via a ▶ search, click "
              "'Save' on their profile and pick the campaign list. Their "
              "activity now feeds your home screen.",
    },
    "connect_etiquette": {
        "title": "Connection requests — the rules that keep you safe",
        "know": [
            "LinkedIn caps invites around 100-200/WEEK; stay well under "
            "(RFP Rockstar's cadence naturally does). A burst of ignored "
            "invites can trigger restrictions.",
            "Withdraw invites older than 3-4 weeks (pending pile hurts "
            "you). Withdrawn contacts can be InMailed instead.",
            "Notes under 260 chars get read; no pitch, no links, one "
            "genuine specific reason. That's exactly what the queue's "
            "connect notes do.",
            "NEVER use browser plugins that auto-send — that's what gets "
            "Navigator accounts banned.",
        ],
        "links": [
            ("Sent invitations (withdraw old ones here)",
             "https://www.linkedin.com/mynetwork/invitation-manager/sent/"),
        ],
        "do": "Once a month: open the link, withdraw anything older than "
              "a month. Matt tracks your daily volume via the queue so "
              "you never flirt with the caps.",
    },
    "inmail": {
        "title": "InMail — when they don't accept",
        "know": [
            "Navigator includes ~50 InMail credits/month; credits come "
            "BACK when someone replies within 90 days — good InMails are "
            "nearly free.",
            "Subject under 8 words; body 60-120 words; one number, one "
            "question. The queue's INMAIL step is pre-written to this "
            "spec.",
            "Open profiles (many public-sector folks) can be InMailed "
            "without spending a credit.",
            "InMail response rates DOUBLE when you've engaged with their "
            "content first (a like or comment days before).",
        ],
        "links": [
            ("Navigator inbox", "https://www.linkedin.com/sales/inbox"),
        ],
        "do": "Only reach for InMail after the connect route stalls "
              "(the queue schedules this automatically as the last step).",
    },
    "warmup": {
        "title": "The warm-up — never arrive totally cold",
        "know": [
            "Before the connect request: view their profile, follow the "
            "org's page, like or comment on ONE recent post. When your "
            "invite arrives they've seen your name twice already.",
            "Comments beat likes: one thoughtful sentence on their post "
            "('This hotspot-lending stat is striking — great program') "
            "makes the later DM feel like a continuation.",
            "15 minutes of warm-up across 5 targets beats 50 cold "
            "invites.",
        ],
        "links": [
            ("Your feed (engage from here)",
             "https://www.linkedin.com/feed/"),
        ],
        "do": "The queue's org-page link is your warm-up stop: open it, "
              "like the latest post, THEN hit ▶ on the connect step.",
    },
    "profile": {
        "title": "Kim's own profile — the landing page they all check",
        "know": [
            "Everyone you touch checks your profile before replying. It "
            "should sell FOR you: headline about the buyer, not the "
            "title — e.g. 'Helping schools & libraries get affordable "
            "student connectivity | Nonprofit carrier on T-Mobile'.",
            "Banner image: Mission Telecom branding. About section: 2-3 "
            "sentences of who you help + one proof number. Featured "
            "section: pin a case study or the savings story.",
            "Turn ON Creator-less simple mode; turn OFF 'viewers of this "
            "profile also viewed' (shows competitors on your page).",
            "Check who viewed your profile weekly — a target who peeked "
            "but didn't reply is warm; DM them a day later.",
        ],
        "links": [
            ("Edit your profile", "https://www.linkedin.com/in/me/"),
            ("Who viewed your profile",
             "https://www.linkedin.com/analytics/profile-views/"),
            ("Your SSI score (LinkedIn's own selling grade)",
             "https://www.linkedin.com/sales/ssi"),
        ],
        "do": "Ask Matt to 'write my LinkedIn headline and about section' "
              "— paste-ready, then click Edit profile and paste.",
    },
    "timing": {
        "title": "Timing & rhythm",
        "know": [
            "Best send windows for education buyers: Tue-Thu, 7-9am or "
            "3-5pm their time (before school starts / after buses roll).",
            "Summer (Jun-Aug) is GOLD for K-12 tech directors — projects "
            "season, calendars open. E-Rate season (Jan-Mar) they're "
            "buried; keep those touches short.",
            "Consistency beats bursts: 10 touches every day beats 50 on "
            "Friday. The queue's DUE NOW list is sized for this.",
        ],
        "links": [],
        "do": "Clear the DUE NOW list each morning with coffee. That's "
              "the whole system.",
    },
    "safety": {
        "title": "Account safety — what gets people banned",
        "know": [
            "Bans come from: automation plugins, invite bursts, copy-"
            "paste identical messages at volume, and scraping. RFP "
            "Rockstar deliberately does NONE of these — Matt writes, "
            "Kim sends by hand, volumes stay human.",
            "Personalizing one line per message (the queue is built for "
            "this) also keeps messages out of spam filters.",
            "If LinkedIn ever shows a warning, stop sending for 48h and "
            "tell Matt — he'll re-pace the queue.",
        ],
        "links": [
            ("Account settings",
             "https://www.linkedin.com/mypreferences/d/categories/account"),
        ],
        "do": "Nothing to do — the system keeps you safe by design. "
              "Just never install 'LinkedIn automation' browser plugins.",
    },
    "replies": {
        "title": "When they reply — landing the meeting",
        "know": [
            "Reply within 4 hours if humanly possible — response speed "
            "is the single biggest meeting-rate lever.",
            "First reply goal is the MEETING, not the pitch: offer two "
            "specific times ('Would Tue 8am or Wed 3:30 work?'). Vague "
            "'sometime next week?' kills momentum.",
            "Paste any reply to Matt — he classifies the objection and "
            "drafts the comeback with the deal's real numbers, and moves "
            "the deal stage.",
        ],
        "links": [
            ("Navigator inbox", "https://www.linkedin.com/sales/inbox"),
            ("Regular LinkedIn messages",
             "https://www.linkedin.com/messaging/"),
        ],
        "do": "Copy their reply → paste to Matt → send his counter → "
              "tell Matt 'they replied' so the stage moves.",
    },
    "teamlink_intel": {
        "title": "Extra Navigator weapons",
        "know": [
            "'View similar' on any good lead finds their counterparts at "
            "other districts — one good tech director profile becomes 20 "
            "more targets.",
            "Account pages in Navigator show all employees by function — "
            "search the district as an ACCOUNT, then browse its people.",
            "Alerts on the home feed flag job changes: a tech director "
            "moving districts is TWO leads (new person at old district, "
            "known friendly at new one).",
            "Notes on lead profiles sync nowhere — keep deal notes in "
            "RFP Rockstar (tell Matt), use Navigator notes only for "
            "personal reminders.",
        ],
        "links": [
            ("Account (company) search",
             "https://www.linkedin.com/sales/search/company"),
            ("Home feed (job-change alerts)",
             "https://www.linkedin.com/sales/home"),
        ],
        "do": "Found a great profile? Click 'View similar' before you "
              "leave the page and send Matt the district names it "
              "surfaces — he'll check them against the board.",
    },
}


def topics() -> list[dict]:
    return [{"key": k, "title": v["title"]} for k, v in KB.items()]


def lookup(topic_keys: list[str] | None = None) -> list[dict]:
    keys = topic_keys or list(KB)
    out = []
    for k in keys:
        if k in KB:
            out.append({"key": k, **KB[k]})
    return out


def build_search(keywords: str | None = None, title: str | None = None,
                 org: str | None = None, exclude: str | None = None) -> dict:
    """Compose a boolean people-search and return Nav + plain URLs."""
    parts = []
    if org:
        parts.append(f'"{org.strip()}"')
    if title:
        alts = [t.strip() for t in title.split(",") if t.strip()]
        if len(alts) > 1:
            parts.append("(" + " OR ".join(f'"{a}"' for a in alts) + ")")
        elif alts:
            parts.append(f'"{alts[0]}"')
    if keywords:
        parts.append(keywords.strip())
    if exclude:
        for x in exclude.split(","):
            if x.strip():
                parts.append(f"NOT {x.strip()}")
    q = " ".join(parts) or "K-12 technology director"
    enc = urllib.parse.quote(q)
    return {"boolean_query": q,
            "sales_nav_url":
                f"https://www.linkedin.com/sales/search/people?keywords={enc}",
            "linkedin_url": ("https://www.linkedin.com/search/results/"
                             f"people/?keywords={enc}"),
            "tip": "Open in Sales Nav, then tighten with the left-side "
                   "Geography filter if needed."}
