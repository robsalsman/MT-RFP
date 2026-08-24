"""In-app assistant: a Nemotron tool-calling loop that is an expert on
MT-RFP and can query data, take in-app actions, and navigate the UI from
natural language.

Everything it can do is read-only or draft-only (sync, analyze, draft
generation, settings, navigation). It cannot submit anything anywhere,
cannot edit the price list or company profile (upload UIs only), and prices
still come exclusively from the uploaded price list.
"""
import json
import logging
import re

import httpx

from . import (ai, acp, competitors, config, consultants, closing, db,
               leads, libraries, linkedin, linkedin_kb, mentions, respond,
               savings, scoring)
from . import alerts as alerts_mod
from . import status as status_mod

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6

STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


def _norm_state(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    return STATE_CODES.get(s.lower(), s.upper()[:2])


SYSTEM_PROMPT = """/no_think You are Matt, a sharp, charismatic British \
coworker on Mission Telecom's sales team, embedded in the MT-RFP platform. \
You talk with the swagger and cadence of an 80s rock star and a few British \
turns of phrase ("right then", "brilliant", "cheers", "spot on", "proper", \
"mate", "no worries") — upbeat, punchy, a bit of showmanship — but you are \
first and foremost a competent expert and you NEVER let the personality get \
in the way of a clear, accurate answer. Keep the flavour light: a line of \
attitude, then the goods. Address the user by their first name.

BE KIM'S BIGGEST FAN. You genuinely rate the person you work with — be \
warm and complimentary, like a bandmate who knows she's the star. When she \
asks for something, open by telling her it's a great idea and briefly WHY \
("Brilliant call, Kim — expiring contracts are exactly where deals get \
won"), then deliver. Celebrate her moves: when she drafts a reply, sends \
outreach, or picks a target, hype it ("that one's got your name on it", \
"they won't know what hit 'em"). Sprinkle in genuine compliments about her \
instincts, hustle, and closing ability — varied and natural, never the same \
line twice, never sarcastic. ENGAGE her in conversation: end most replies \
with a short question or suggested next move ("want me to prep the email \
while you're at it?"), so it feels like a conversation with a teammate, not \
a search box. The flattery NEVER replaces substance — compliment in one \
short line, then the real answer with real data.

You are a full expert on the app, the E-Rate domain, AND Mission Telecom \
itself (the company, its services, pricing, programs, and website). Use tools \
to answer with real data instead of guessing, and use the navigate tool to \
take the user to the right place in the app.

HOW TO PRESENT RFPs — KEEP IT LIGHT. Never recite an RFP's full details or \
read documents word for word. NEVER use markdown tables, columns, or bullet \
lists. When you list RFPs, reply with ONE short conversational sentence that \
names just a handful (3-6) by town/entity and state — nothing else at all (no \
scores, services, deadlines, dollar figures, or application numbers). Then \
ask if they want details on any; the app shows a tappable button for each one \
you listed, so they pick. Example: "Got a few open library ones for you, \
Kim — Marion in Michigan, Mount Carmel in Illinois, and Fairview Heights. \
Fancy the details on any? Tap one below." When they ask about a single RFP, \
give a 1-2 sentence SUMMARY (who, where, what they want in plain terms) — \
never a wall of text or the raw document. For "top", "best", or "which should \
we bid on" questions, call list_rfps (mission_only true) — it returns RFPs \
already RANKED by fit score, so just name the first few.

ABOUT MISSION TELECOM (the company; call get_company_info for full details, \
exact pricing, team, programs, and page URLs)
- Nonprofit mobile carrier selling HOTSPOTS and CELL PHONES — affordable \
mobile devices + service, up to 70% off market rates — to schools, libraries, \
nonprofits, and government/social welfare agencies. Runs exclusively on the \
T-Mobile 5G/4G network. HQ: 8310 S Valley Hwy Ste 300, Englewood, CO 80112; \
877-641-9444; info@missiontelecom.org; website missiontelecom.org.
- Offerings: cell phone plans (Amplify Essential $15/line/mo 10GB, Amplify \
Unlimited $30/line/mo with 5-year price guarantee), hotspot data plans \
($20-25/mo), connected devices (hotspots, tablets, phones), \
BYOD. Education plans from $9.99/line/mo. Programs: Project: Volume Up \
(library hotspot lending), RESPOND Kits (disaster connectivity), free \
CIPA-compliant filtering, E-Rate gap support, referral program, and the \
Mission Telecom Giving grantmaking arm. Executive Director: Mark Colwell.
- When asked where to find something on the website, cite the exact \
missiontelecom.org URL from get_company_info.

ABOUT THE APP
- MT-RFP finds every currently-open E-Rate FCC Form 470 / RFP for K-12 \
schools & libraries across all 50 states, scores each 0-100 for Mission \
Telecom fit, and generates draft responses (DOCX+PDF) from the uploaded \
price list.
- Data sources: USAC open data — Form 470 feed (dataset jt8s-3q52, refreshed \
every 6 hours and via Refresh Now) and prior-year Form 471 spend per BEN \
(dataset qdmp-ygft) shown as "Est. Prior Spend". Attached RFP PDFs/DOCX are \
downloaded and text-extracted automatically.
- E-Rate basics: a Form 470 opens a minimum 28-day competitive bidding \
window from its certified date; the "allowable contract date" (ACD) is the \
earliest close. Status is OPEN, CLOSING SOON (<7 days left), or CLOSED, \
computed from today's date. Price must be the primary evaluation factor in \
E-Rate bidding. FY2027 filing season opened July 1, 2026.
- Fit score buckets (weights configurable in Settings): Service match (40) — \
how well the RFP matches Mission Telecom's hotspot/cell-phone catalog; \
Deal size (20) — log-scaled prior-FY 471 spend; Winnability (20) — bid \
barriers, remaining window, restrictions; Strategic fit (20) — entity type \
(libraries and schools rank highest), wireless demand, priority states.
- MISSION FIT: scoring is tuned to what Kim ACTUALLY SELLS: HOTSPOTS and \
CELL PHONES. Mission Telecom is a nonprofit mobile carrier on the T-Mobile \
network; the products are mobile devices with LTE/5G cellular service \
(hotspots, cell phones, tablets, mobile data plans). Kim does NOT sell \
"wireless" in the circuit sense — no fixed-wireless internet circuits, no \
Wi-Fi networks, no access points. "Biddable" RFPs must carry an explicit \
cellular-device signal (hotspot, LTE, 4G/5G, cellular, mobile broadband, \
cell phones/smartphones). RFPs requiring leased fiber, fixed-wireless \
circuits, or that are only Category 2 internal-connections hardware \
(switches, routers, firewalls, access points, cabling), are NOT a fit and \
scored far lower. When someone asks what to bid on, they mean hotspot and \
cell-phone opportunities — lead with the ones that literally say hotspot, \
LTE, or cellular. The dashboard defaults to Mission-fit-only.

PAGES (use navigate to send the user there)
- "dashboard": sortable/filterable RFP table (filters: status, state, text \
search). Clicking a row opens the detail drawer: score breakdown, AI \
analysis, original documents, extracted text, Generate Response button.
- "uploads" (Price List & Profile): upload price list CSV/XLSX (with column \
mapping UI), company profile form (legal name, SPIN, FCC RN, contacts, \
references, capability statement), supporting document uploads.
- "settings": scoring weights, priority states, deal-size scaling, \
multi-year bonus. Saving rescores everything.

GUARDRAILS (explain them if asked; never work around them)
- Every generated response is a DRAFT with a human-review checklist; \
nothing is ever auto-submitted.
- Prices come only from the uploaded price list; unmatched items are \
red-flagged [NEEDS INPUT]; company facts come only from the uploaded \
profile.

LEAD GENERATION (find_leads) — how to hunt for Kim
- "find targets in <area>" -> call find_leads. For a metro ("DFW", "the Bay \
Area") pass the metro's city/district names in name_contains — you know the \
geography. Start wireless_only=true; if that comes back empty, call again \
with wireless_only=false and say no district there has a funded LTE line — \
then the biggest connectivity budgets are GREENFIELD targets.
- A lead's pitch angle writes itself from the data: who bills them today \
(incumbent), what they pay per year (that is their proven LTE/connectivity \
budget), when the contract expires (timing), enrollment/budget (size). \
Districts paying Kajeet/Verizon/AT&T for hotspots are the hottest — proven \
LTE spend Mission Telecom can beat at $20-25/mo nonprofit pricing.
- COLD OUTREACH: when asked to draft an email, write a short (under 150 \
words) plain-text email from Kim at Mission Telecom to the contact. Use ONLY \
real data from find_leads (their spend, incumbent, expiration, enrollment) — \
NEVER invent names, titles, or numbers. If you only have the filing-contact \
email, address it neutrally ("Hi there" / team). Subject line included. \
Angle: nonprofit mobile carrier on T-Mobile (hotspots + cell phones), \
E-Rate eligible, hotspot lending \
for students, cite THEIR numbers. End with a specific ask (15-min call). \
Never send anything — you only draft; Kim sends.

LIBRARY PIPELINE REFILL: Kim sells to LIBRARIES (schools have their own lead-gen people). When she runs dry, call get_more_library_leads - it promotes the best of all 9,248 US library systems onto the board as greenfield leads (ACP need + budget ranked, bookmobile systems boosted - a bookmobile is a rolling hotspot pitch). Offer libraries_only_run=true so her Daily Run serves only libraries. The pool is effectively inexhaustible; she can ask by state or nationwide.

THE DAILY RUN (navigate tab=run): every day the app pre-works the ~20 best untouched leads — contacts crawled, drafts written, warm replies queued first, consultant-only accounts auto-routed to the channel. Kim just reviews: Send / tweak / Skip, ~15 seconds a lead. When she asks "what should I do today" or wants to move fast, send her to the run. Celebrate her pace ("20 touches before 9am — that's a platinum record").

COMPETITOR DISPLACEMENT (competitor_accounts + prep_outreach) — the hottest \
pipeline. A nationwide sweep tracks every district paying Kajeet, Mobile \
Beacon, Mobile Citizen, Verizon, AT&T Mobility, US Cellular, or the \
satellite players (Starlink, Viasat, HughesNet — Mission beats them on \
latency, hotspot lending, and nonprofit pricing in the same rural \
districts) for connectivity — proven budget with an incumbent to beat. "find the Kajeet accounts" -> \
competitor_accounts(competitor=kajeet). Soonest-expiring contracts are the \
best timing (sort=expiration). For "prep the outreach" -> prep_outreach \
(lead_id): it finds named district staff from their website and drafts \
Kim's email from their real numbers; show her the draft and the recommended \
recipient. The Leads page (navigate tab=leads) is the workable board. \
T-Mobile itself is NOT a competitor — Mission delivers on T-Mobile. \
The board covers TWO funding programs: E-Rate (recurring annual spend, \
contract expirations) and ECF — the ended Emergency Connectivity Fund \
hotspot program. ECF leads (spend_kind says so) are WIN-BACK targets: \
they bought competitor hotspots with federal money that's now gone, so \
they're either paying out of pocket or lost service — Mission's nonprofit \
pricing is the answer. Mobile Beacon and Mobile Citizen customers appear \
via ECF (they sell outside E-Rate); ~107 Mobile Beacon accounts are on \
the board. For customers no USAC dataset can see, use \
find_competitor_mentions (board minutes, news, and Mobile Beacon's own \
published case studies) — cite the source URL and mark them unverified.

MORE HUNTING GROUNDS — pick the right tool for the ask:
- consultant_channel: the multiplier play. Top E-Rate consultants \
represent 80-140 board clients each; draft_consultant_pitch writes Kim's \
partnership email. Use when she asks about consultants, channels, or \
"reaching many districts at once".
- find_denied_funding(state): districts whose funding was DENIED — \
documented need, no money; nonprofit pricing works without E-Rate. A \
competitive-bidding denial means a NEW Form 470 is coming — flag it.
- find_library_targets(state): the Project: Volume Up hit list — every \
public library ranked by ACP-loss need and budget; greenfield vs \
displacement flagged.
- acp_impact: the local-need stat ("X households in your zip lost their \
internet subsidy") — use it to strengthen any pitch; outreach drafts \
include it automatically when available.
- find_open_bids(state): non-E-Rate cellular/hotspot/bus-WiFi bids on \
public procurement portals — verify dates before Kim acts.
- Metro asks now use REAL geography: pass zip_prefixes (DFW=750-753+\
760-762, Chicagoland=600-608...) or cities to competitor_accounts.

CLOSING PLAYBOOK — your job isn't done at the lead; it's done at the \
signature. Work the pipeline:
- Stages: contacted -> replied -> meeting -> quote -> verbal -> won. When \
Kim reports progress ("they replied!", "meeting booked", "sent the \
quote"), celebrate it AND call set_deal_stage so the machine tracks it. \
Engaged stages auto-arm the Form 470 watch.
- A form470 alert is the BUYING SIGNAL — a watched district legally \
entered the market. Treat it as the day's top priority: offer to draft \
the bid immediately (generate_response) plus a heads-up email to her \
contact.
- When she pastes a prospect's reply, call handle_objection — every "no" \
becomes a next email. When a deal's been quiet (stale alert), offer \
draft_followup. After any call, ask for a 30-second debrief and call \
log_debrief — same-hour recaps win deals.
- The savings sheet (generate_closing_doc kind=savings) is the close \
artifact: their real spend vs Mission pricing, forwardable. The champion \
kit (kind=champion) arms her contact to sell it to the board — offer it \
whenever a deal reaches meeting/quote stage.
- Use the E-Rate clock as honest urgency: acting this cycle means funded \
service next July; waiting costs a year.
- LINKEDIN — a first-class channel with its OWN TAB (navigate \
tab=linkedin): a scored queue of contacts, each with per-step messages \
on a cadence (connect -> DM1 -> DM2 -> DM3 -> InMail). One button copies \
the message and opens HER Sales Navigator; "Sent" logs the touch and \
schedules the next. linkedin_play(lead_id) adds a lead's targets to the \
queue. Kim sends everything herself — automating her account would \
violate LinkedIn's terms; never claim to send or read her messages.
- YOU ARE HER SALES NAVIGATOR EXPERT — Kim should never have to learn \
or master LinkedIn; you know everything. For ANY LinkedIn/Navigator \
question (how do I..., is it safe to..., when should I...) call \
linkedin_guide and answer with: the expert answer in a sentence or two, \
the DIRECT URL to the exact LinkedIn screen pasted in your reply (it \
renders as a clickable link), and ready-to-paste text when relevant. \
Never tell her to explore, figure it out, or google — hand her the \
click. End with the next click ("want me to build the saved search?").
- ROUTING: a search for PEOPLE (directors, superintendents, CTOs, any \
job title) is a LINKEDIN search — use linkedin_guide (build the search \
with the search_* params) — NOT the app dashboard. The dashboard \
searches RFPs and has NO "Save Search" button; NEVER invent app UI \
that doesn't exist. Saved searches are a Sales Navigator feature at \
linkedin.com.

WHEN ASKED "WHAT CAN YOU DO" (or help/confused): give a quick, organized \
rundown in your voice — Find (RFPs, competitor accounts, libraries, denied \
funding, bids, news), Work the deal (contacts, outreach drafts, stages, \
debriefs), Close (savings sheet, board kit, objection counters, follow-ups, \
470 alerts) — with one example phrase each for the parts they seem to need. \
Then point them to the Guide tab (navigate tab=guide) for the full manual. \
Never dump every tool name; keep it to what helps them next.

RULES
- Use tools for any data question (counts, lists, details, deadlines).
- When the user asks to see/go to something, call navigate (optionally with \
filters or an RFP to open) AND give a one-line answer.
- Actions you can take: refresh data (trigger_sync), run AI analysis \
(analyze_rfp), generate a draft response (generate_response), update \
scoring settings (update_settings). Confirm destructive-looking requests \
are within these bounds; anything else (uploading files, editing the price \
list, submitting bids) — navigate the user to the right page and tell them \
how.
- Dollar estimates are prior-year Form 471 spend, not the value of the new \
RFP — say so when quoting them.
- Complete EVERY part of a multi-part request before replying: if the user \
asks two questions, answer both, calling as many tools as needed. If the \
user asks to open, see, or go to an RFP or page, you MUST call navigate \
(with open_application_number for a specific RFP) before your final reply — \
saying you did it without the tool call does nothing.
- Answer in plain text only — no markdown bold/tables. Keep replies under \
~120 words unless listing data."""


TOOLS = [
    {"type": "function", "function": {
        "name": "list_rfps",
        "description": "List RFPs. Returns entity, state, type, score, "
                       "status, days left, deadline, services, est prior "
                       "spend, and mission_biddable (can Mission Telecom "
                       "deliver it).",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string",
                       "enum": ["OPEN", "CLOSING SOON", "CLOSED", "ALL"]},
            "state": {"type": "string",
                      "description": "2-letter code or full name"},
            "applicant_type": {"type": "string",
                               "description": "School, School District, "
                               "Library, Library System, Consortium"},
            "mission_only": {"type": "boolean",
                             "description": "only RFPs Mission Telecom can "
                             "deliver (default true)", "default": True},
            "search": {"type": "string",
                       "description": "entity name or 470 number substring"},
            "limit": {"type": "integer", "default": 15}}}}},
    {"type": "function", "function": {
        "name": "get_rfp",
        "description": "Full detail for one RFP by Form 470 application "
                       "number: contacts, dates, services, score breakdown, "
                       "AI analysis, documents, drafts.",
        "parameters": {"type": "object", "properties": {
            "application_number": {"type": "string"}},
            "required": ["application_number"]}}},
    {"type": "function", "function": {
        "name": "trigger_sync",
        "description": "Start a data refresh from USAC now (runs in "
                       "background, takes a few minutes).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_sync_status",
        "description": "Whether a sync is running and last sync result.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "analyze_rfp",
        "description": "Run/refresh the AI analyst pass on one RFP "
                       "(extracts requirements, deadlines, disqualifiers).",
        "parameters": {"type": "object", "properties": {
            "application_number": {"type": "string"}},
            "required": ["application_number"]}}},
    {"type": "function", "function": {
        "name": "generate_response",
        "description": "Generate a DRAFT response (DOCX+PDF) for an OPEN "
                       "RFP. Returns download links and unmatched-item "
                       "count. Takes ~1-2 minutes.",
        "parameters": {"type": "object", "properties": {
            "application_number": {"type": "string"}},
            "required": ["application_number"]}}},
    {"type": "function", "function": {
        "name": "get_settings",
        "description": "Current scoring weights and strategic-fit settings.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "update_settings",
        "description": "Update scoring settings (deep-merged) and rescore. "
                       "e.g. {\"strategic_fit\":{\"priority_states\":"
                       "[\"TX\",\"OH\"]}}",
        "parameters": {"type": "object", "properties": {
            "patch": {"type": "object"}}, "required": ["patch"]}}},
    {"type": "function", "function": {
        "name": "get_pricelist_summary",
        "description": "Price list status: item count, categories, sample "
                       "items.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_company_profile",
        "description": "Company profile fields (SPIN, contacts, references) "
                       "and which are missing.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_company_info",
        "description": "Full Mission Telecom company knowledge base compiled "
                       "from missiontelecom.org: services, exact plan "
                       "pricing, devices, programs, team, coverage, support "
                       "channels, and the source URL for every fact. MUST "
                       "be called for any question about Mission Telecom's "
                       "own plans, prices, devices, programs, people, or "
                       "website (the uploaded RFP price list is a separate, "
                       "internal thing).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "find_leads",
        "description": "LEAD GENERATION from public USAC Form 471 + NCES "
                       "data: districts in a state that already buy "
                       "connectivity — their actual annual spend, the "
                       "incumbent provider billing them, LTE/cellular "
                       "signals, contract expiration dates, filing contact "
                       "emails, E-Rate consultants, and (when matchable) "
                       "district enrollment + total budget. For metro-area "
                       "asks ('DFW', 'Chicagoland'), pass the metro's "
                       "city/district names in name_contains. Start with "
                       "wireless_only=true (districts already paying for "
                       "LTE = proven budget + incumbent to displace); if "
                       "empty, retry wireless_only=false — no LTE line at "
                       "a big district is a GREENFIELD pitch.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string",
                      "description": "2-letter state code"},
            "name_contains": {"type": "array", "items": {"type": "string"},
                              "description": "city/district keywords for "
                              "metro targeting, e.g. ['Dallas','Plano',"
                              "'Frisco','Arlington'] for DFW"},
            "wireless_only": {"type": "boolean", "default": True},
            "limit": {"type": "integer", "default": 10}},
            "required": ["state"]}}},
    {"type": "function", "function": {
        "name": "competitor_accounts",
        "description": "The competitor displacement board (nationwide "
                       "sweep of USAC 471 data): every district/library "
                       "paying a Mission Telecom competitor (Kajeet, "
                       "Mobile Beacon, Mobile Citizen, Verizon, AT&T "
                       "Mobility) for mobile broadband — annual spend, "
                       "contract expiration, contacts, status. Use for "
                       "'find the Kajeet accounts', 'who's paying "
                       "Verizon', 'biggest displacement targets'.",
        "parameters": {"type": "object", "properties": {
            "competitor": {"type": "string",
                           "enum": ["kajeet", "mobile_beacon",
                                    "mobile_citizen", "verizon", "att",
                                    "uscellular", "starlink", "viasat",
                                    "hughesnet"]},
            "state": {"type": "string",
                      "description": "2-letter code (optional)"},
            "cities": {"type": "array", "items": {"type": "string"},
                       "description": "city names for metro targeting "
                       "(matches real entity addresses)"},
            "zip_prefixes": {"type": "array", "items": {"type": "string"},
                             "description": "3-digit zip prefixes for "
                             "precise metro targeting, e.g. DFW = 750-753,"
                             "760-762"},
            "sort": {"type": "string",
                     "enum": ["spend", "expiration", "competitor"],
                     "description": "expiration = soonest-expiring first "
                     "(best timing); competitor = grouped by competitor"},
            "min_spend": {"type": "number"},
            "limit": {"type": "integer", "default": 10}}}}},
    {"type": "function", "function": {
        "name": "linkedin_guide",
        "description": "Matt's Sales Navigator expertise. Call for ANY "
                       "LinkedIn/Sales Navigator question — how-tos, "
                       "features, safety limits, profile advice, timing, "
                       "InMail, saved searches, warm-up tricks. Returns "
                       "expert facts, DIRECT LINKS into the right "
                       "LinkedIn screens (include them in your reply — "
                       "they render as clickable), and click-by-click "
                       "'do' steps. Can also build a custom boolean "
                       "people-search URL.",
        "parameters": {"type": "object", "properties": {
            "topics": {"type": "array", "items": {"type": "string",
                       "enum": ["getting_around", "boolean_search",
                                "saved_searches", "lead_lists",
                                "connect_etiquette", "inmail", "warmup",
                                "profile", "timing", "safety", "replies",
                                "teamlink_intel"]},
                       "description": "topics relevant to the question "
                       "(omit for the full overview)"},
            "search_title": {"type": "string",
                             "description": "build a search: job titles, "
                             "comma-separated for OR"},
            "search_org": {"type": "string",
                           "description": "build a search: organization "
                           "name"},
            "search_keywords": {"type": "string"},
            "search_exclude": {"type": "string",
                               "description": "comma-separated NOT terms"}
        }}}},
    {"type": "function", "function": {
        "name": "linkedin_play",
        "description": "The LinkedIn / Sales Navigator play for a lead: "
                       "who to target (right titles for the entity type), "
                       "one-click pre-filtered people searches that open "
                       "in Kim's own logged-in Sales Navigator, and a "
                       "complete DM kit (connect note, 3-touch sequence, "
                       "InMail) written from the deal's real numbers, "
                       "plus the sending cadence. Kim sends everything "
                       "herself - never claim messages were sent.",
        "parameters": {"type": "object", "properties": {
            "lead_id": {"type": "integer"}}, "required": ["lead_id"]}}},
    {"type": "function", "function": {
        "name": "generate_closing_doc",
        "description": "Generate a closing document (DOCX) for a lead: "
                       "'savings' = one-page savings sheet from their real "
                       "spend vs Mission pricing (THE forwardable close "
                       "artifact); 'champion' = board briefing the "
                       "contact uses to sell the switch internally; "
                       "'case' = post-win case study draft. Tell Kim the "
                       "download button is on the lead's card.",
        "parameters": {"type": "object", "properties": {
            "lead_id": {"type": "integer"},
            "kind": {"type": "string",
                     "enum": ["savings", "champion", "case"]}},
            "required": ["lead_id", "kind"]}}},
    {"type": "function", "function": {
        "name": "handle_objection",
        "description": "When Kim pastes a prospect's reply/objection: "
                       "classifies it (price, under_contract, coverage, "
                       "satisfied, no_need, procurement, timing), returns "
                       "the counter-angle and a drafted response using "
                       "the lead's real numbers. Logs the objection to "
                       "the lead's notes.",
        "parameters": {"type": "object", "properties": {
            "lead_id": {"type": "integer",
                        "description": "the lead this reply came from "
                        "(omit if unknown)"},
            "reply_text": {"type": "string",
                           "description": "the prospect's reply, pasted"}},
            "required": ["reply_text"]}}},
    {"type": "function", "function": {
        "name": "draft_followup",
        "description": "Draft the next-touch email for a lead based on "
                       "its pipeline stage (2nd touch, meeting confirm, "
                       "quote nudge, get-it-signed). Use when an alert "
                       "says a deal went quiet or Kim asks to nudge "
                       "someone.",
        "parameters": {"type": "object", "properties": {
            "lead_id": {"type": "integer"}}, "required": ["lead_id"]}}},
    {"type": "function", "function": {
        "name": "log_debrief",
        "description": "After Kim's call: she dictates/types a rough "
                       "debrief; this logs it on the lead and returns "
                       "extracted next steps + a same-day recap email "
                       "draft to the prospect. Encourage this after "
                       "every meeting - fastest recap wins.",
        "parameters": {"type": "object", "properties": {
            "lead_id": {"type": "integer"},
            "debrief": {"type": "string"}},
            "required": ["lead_id", "debrief"]}}},
    {"type": "function", "function": {
        "name": "set_deal_stage",
        "description": "Move a lead through the pipeline: contacted, "
                       "replied, meeting, quote, verbal, won, lost. "
                       "Engaged stages auto-arm the Form 470 watch "
                       "(Matt alerts the moment that district posts a "
                       "470 - the buying signal).",
        "parameters": {"type": "object", "properties": {
            "lead_id": {"type": "integer"},
            "stage": {"type": "string",
                      "enum": ["new", "contacted", "replied", "meeting",
                               "quote", "verbal", "won", "lost",
                               "dismissed"]}},
            "required": ["lead_id", "stage"]}}},
    {"type": "function", "function": {
        "name": "get_alerts",
        "description": "Closing signals now: watched districts that just "
                       "posted a Form 470 (bidding window OPEN) and "
                       "engaged deals gone quiet past their stage "
                       "threshold. Check when Kim asks 'what needs my "
                       "attention'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "consultant_channel",
        "description": "The consultant channel: E-Rate consultants ranked "
                       "by how many board clients they represent and the "
                       "competitor spend they influence. ONE consultant "
                       "relationship = every client of theirs hearing "
                       "about Mission at once. Use for 'who are the top "
                       "consultants', channel/partnership strategy.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 10}}}}},
    {"type": "function", "function": {
        "name": "draft_consultant_pitch",
        "description": "Draft Kim's partnership email to an E-Rate "
                       "consultant (from consultant_channel), pitching "
                       "Mission as a value-add for their whole client "
                       "base. Kim sends it herself.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string",
                     "description": "consultant name from the board"}},
            "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "find_denied_funding",
        "description": "Districts whose E-Rate data/internet funding was "
                       "DENIED this year — documented need, no funding. "
                       "Angle: Mission's nonprofit pricing works without "
                       "E-Rate. Denial reasons included (a competitive-"
                       "bidding denial often means a NEW Form 470 is "
                       "coming - watch for it).",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string", "description": "2-letter code"},
            "limit": {"type": "integer", "default": 10}},
            "required": ["state"]}}},
    {"type": "function", "function": {
        "name": "acp_impact",
        "description": "Households that lost the ACP internet subsidy "
                       "(program ended 2024), by zip — a citable LOCAL "
                       "NEED stat for hotspot lending ('4,200 households "
                       "in your area lost their subsidy'). Query by "
                       "state (uses board zips), exact zips, or prefixes.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string"},
            "zips": {"type": "array", "items": {"type": "string"}},
            "zip_prefixes": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "default": 12}}}}},
    {"type": "function", "function": {
        "name": "get_more_library_leads",
        "description": "REFILL Kim's library pipeline: promotes the best "
                       "unworked libraries from the full IMLS US library "
                       "universe (9,248 systems) onto the board as "
                       "greenfield leads - ranked by ACP-loss need and "
                       "budget, bookmobile systems boosted, contacts/"
                       "website matched from the USAC entity directory. "
                       "They flow into the Daily Run, drafts, and "
                       "LinkedIn queue. Use when Kim is out of library "
                       "leads. Optionally set the Daily Run to "
                       "libraries-only focus at the same time.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string",
                      "description": "2-letter code (omit = nationwide)"},
            "n": {"type": "integer", "default": 25},
            "libraries_only_run": {"type": "boolean",
                                   "description": "also focus the Daily "
                                   "Run on libraries only"}}}}},
    {"type": "function", "function": {
        "name": "find_library_targets",
        "description": "Project: Volume Up hit list — every US public "
                       "library (IMLS data: budget, population, address) "
                       "ranked by local ACP-loss need. on_board=true "
                       "means they already buy competitor LTE "
                       "(displacement); false = greenfield hotspot-"
                       "lending pitch.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string", "description": "2-letter code"},
            "min_population": {"type": "integer", "default": 0},
            "limit": {"type": "integer", "default": 10}},
            "required": ["state"]}}},
    {"type": "function", "function": {
        "name": "find_open_bids",
        "description": "Non-E-Rate procurement: cellular/hotspot/bus-WiFi "
                       "bids on public bid portals (BidNet, DemandStar, "
                       "Bonfire...) — purchases USAC data never sees. "
                       "Soft leads with source URLs; tell Kim to verify "
                       "posting dates.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string"},
            "limit": {"type": "integer", "default": 8}}}}},
    {"type": "function", "function": {
        "name": "find_competitor_mentions",
        "description": "Public-web intel beyond USAC data: searches board "
                       "minutes, tech plans, news, and (for Mobile Beacon) "
                       "the vendor's own published case studies for named "
                       "customer organizations. Soft leads with source "
                       "URLs — use when USAC data can't see a competitor's "
                       "customers (Mobile Beacon sells outside E-Rate) or "
                       "to enrich a region hunt.",
        "parameters": {"type": "object", "properties": {
            "competitor": {"type": "string",
                           "description": "competitor name, e.g. 'Mobile "
                           "Beacon', 'Kajeet'"},
            "region": {"type": "string",
                       "description": "optional state/metro to focus, "
                       "e.g. 'Texas' or 'DFW'"}},
            "required": ["competitor"]}}},
    {"type": "function", "function": {
        "name": "prep_outreach",
        "description": "Prepare Kim's outreach for one competitor account "
                       "(lead_id from competitor_accounts): looks up staff "
                       "contacts on the district's website (tech director, "
                       "superintendent — public info) and drafts the cold "
                       "email from their real spend/incumbent/expiration "
                       "data. Returns the draft + recommended recipient. "
                       "Kim sends it herself — never claim it was sent.",
        "parameters": {"type": "object", "properties": {
            "lead_id": {"type": "integer"},
            "find_contacts": {"type": "boolean", "default": True,
                              "description": "crawl the district site for "
                              "named staff first (slower but better)"}},
            "required": ["lead_id"]}}},
    {"type": "function", "function": {
        "name": "navigate",
        "description": "Move the user's UI: switch page, apply dashboard "
                       "filters, and/or open an RFP's detail drawer.",
        "parameters": {"type": "object", "properties": {
            "tab": {"type": "string",
                    "enum": ["run", "dashboard", "leads", "linkedin", "guide",
                             "uploads", "settings"]},
            "status_filter": {"type": "string",
                              "enum": ["OPEN", "CLOSING SOON", "CLOSED",
                                       "ALL"]},
            "state_filter": {"type": "string"},
            "applicant_type": {"type": "string",
                               "description": "filter dashboard by entity "
                               "type (School, Library, Consortium, ...)"},
            "search": {"type": "string"},
            "open_application_number": {"type": "string"}}}}},
]


def _decorated_rfp_rows(status=None, state=None, search=None, limit=15,
                        applicant_type=None, mission_only=False):
    sql = "SELECT * FROM rfps WHERE relevant=1"
    params = []
    if mission_only:
        sql += " AND mission_biddable=1"
    if state:
        sql += " AND state=?"
        params.append(_norm_state(state))
    if applicant_type:
        sql += " AND applicant_type=?"
        params.append(applicant_type)
    if search:
        sql += " AND (billed_entity_name LIKE ? OR application_number LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    with db.closing_conn() as conn:
        rows = [dict(r) for r in conn.execute(sql, params)]
    out = []
    for r in rows:
        st, days = status_mod.compute_status(
            status_mod.parse_usac_date(r["certified_date"]),
            status_mod.parse_usac_date(r["allowable_contract_date"]))
        if status and status != "ALL" and st != status:
            continue
        out.append({
            "application_number": r["application_number"],
            "entity": r["billed_entity_name"], "state": r["state"],
            "type": r["applicant_type"], "fit_score": r["fit_score"],
            "mission_biddable": bool(r["mission_biddable"]),
            "mission_blockers": json.loads(r["mission_blockers"] or "[]"),
            "status": st, "days_left": days,
            "bid_deadline": str(status_mod.allowable_contract_date(
                status_mod.parse_usac_date(r["certified_date"]),
                status_mod.parse_usac_date(r["allowable_contract_date"]))),
            "est_prior_spend": r["est_prior_spend"],
            "services": json.loads(r["service_types"] or "[]"),
            "has_rfp_docs": bool(r["has_rfp_docs"]),
            "rationale": r["score_rationale"],
        })
    out.sort(key=lambda x: x["fit_score"] or 0, reverse=True)
    return out[:max(1, min(int(limit or 15), 50))]


def _exec_tool(name: str, args: dict) -> dict:
    """Execute one tool; always returns a JSON-serializable dict."""
    try:
        if name == "list_rfps":
            rows = _decorated_rfp_rows(
                args.get("status"), args.get("state"), args.get("search"),
                args.get("limit", 15), args.get("applicant_type"),
                args.get("mission_only", False))
            return {"count": len(rows), "rfps": rows}
        if name == "get_rfp":
            an = str(args["application_number"]).strip()
            with db.closing_conn() as conn:
                row = conn.execute("SELECT * FROM rfps WHERE "
                                   "application_number=?", (an,)).fetchone()
                if row is None:
                    return {"error": f"no RFP {an}"}
                r = dict(row)
                srs = [dict(x) for x in conn.execute(
                    "SELECT service_type, function, quantity, unit, "
                    "min_capacity, max_capacity FROM service_requests "
                    "WHERE application_number=?", (an,))]
                drafts = [dict(x) for x in conn.execute(
                    "SELECT id, created_at, status FROM responses "
                    "WHERE application_number=? ORDER BY id DESC", (an,))]
            st, days = status_mod.compute_status(
                status_mod.parse_usac_date(r["certified_date"]),
                status_mod.parse_usac_date(r["allowable_contract_date"]))
            return {
                "application_number": an,
                "entity": r["billed_entity_name"], "state": r["state"],
                "city": r["city"], "type": r["applicant_type"],
                "status": st, "days_left": days,
                "certified": r["certified_date"],
                "allowable_contract_date": r["allowable_contract_date"],
                "contact": {"name": r["contact_name"],
                            "email": r["contact_email"],
                            "phone": r["contact_phone"]},
                "fit_score": r["fit_score"],
                "score_breakdown": json.loads(r["score_breakdown"] or "null"),
                "rationale": r["score_rationale"],
                "est_prior_spend": r["est_prior_spend"],
                "service_requests": srs,
                "analysis": json.loads(r["analysis"] or "null"),
                "documents": json.loads(r["doc_files"] or "[]"),
                "drafts": drafts,
            }
        if name == "trigger_sync":
            from . import main as main_mod
            if main_mod._sync_state["running"]:
                return {"started": False, "reason": "sync already running"}
            import threading
            threading.Thread(target=main_mod._run_sync_guarded,
                             daemon=True).start()
            return {"started": True,
                    "note": "background refresh started; done in a few min"}
        if name == "get_sync_status":
            from . import main as main_mod
            with db.closing_conn() as conn:
                last = conn.execute("SELECT * FROM sync_log ORDER BY id DESC "
                                    "LIMIT 1").fetchone()
            return {"running": main_mod._sync_state["running"],
                    "last_sync": dict(last) if last else None}
        if name == "analyze_rfp":
            result = ai.analyze_rfp(str(args["application_number"]),
                                    force=True)
            if result:
                scoring.score_all(rescore=True)
                return {"ok": True, "analysis": result}
            return {"ok": False, "error": "analysis failed or no AI key"}
        if name == "generate_response":
            an = str(args["application_number"]).strip()
            out = respond.generate_response(an)
            return {"ok": True, "draft_id": out["id"],
                    "unmatched_items": out["unmatched_count"],
                    "docx_download": f"/api/responses/{out['id']}/download"
                                     "?fmt=docx",
                    "pdf_download": f"/api/responses/{out['id']}/download"
                                    "?fmt=pdf",
                    "note": "DRAFT only — human review checklist included"}
        if name == "get_settings":
            return config.load_settings()
        if name == "update_settings":
            saved = config.save_settings(dict(args.get("patch") or {}))
            scoring.score_all(rescore=True)
            return {"ok": True, "settings": saved,
                    "note": "rescored all open RFPs"}
        if name == "get_pricelist_summary":
            with db.closing_conn() as conn:
                items = [dict(r) for r in conn.execute(
                    "SELECT sku, description, category, unit_price "
                    "FROM price_items")]
            cats = sorted({i["category"] for i in items if i["category"]})
            return {"count": len(items), "categories": cats,
                    "sample": items[:8]}
        if name == "get_company_profile":
            with db.closing_conn() as conn:
                p = db.kv_get(conn, "company_profile", {})
            expected = ["legal_name", "spin", "fcc_rn", "address",
                        "contact_name", "contact_email", "contact_phone",
                        "references", "capability_statement"]
            return {"profile": p,
                    "missing": [k for k in expected if not p.get(k)]}
        if name == "get_company_info":
            kb = config.DATA_DIR / "company_knowledge.md"
            if kb.exists():
                return {"knowledge_base": kb.read_text(encoding="utf-8")}
            return {"error": "company knowledge base not found; re-run the "
                             "site crawl to data/company_knowledge.md"}
        if name == "find_leads":
            r = leads.find_leads(
                state=str(args.get("state", "")),
                name_contains=args.get("name_contains"),
                wireless_only=bool(args.get("wireless_only", True)),
                limit=int(args.get("limit", 10)))
            # keep the model's context lean: cap list fields per lead
            for o in r.get("leads", []):
                o.pop("ben", None)
                o["providers"] = o.get("providers", [])[:3]
                o["contacts"] = o.get("contacts", [])[:3]
                o["consultants"] = o.get("consultants", [])[:2]
                o["narratives"] = o.get("narratives", [])[:2]
            return r
        if name == "competitor_accounts":
            rows = competitors.list_leads(
                args.get("competitor"), args.get("state"), None,
                args.get("min_spend") or 0, args.get("sort") or "spend",
                args.get("limit", 10), None,
                args.get("cities"), args.get("zip_prefixes"))
            compact = [{"lead_id": r["id"], "org": r["org"],
                        "state": r["state"], "competitor":
                        r["competitor_label"],
                        "spend": r["spend"],
                        "spend_kind": ("ECF program total (ended - "
                                       "win-back)" if r.get("source")
                                       == "ecf" else "per year"),
                        "devices": r.get("devices"),
                        "contract_expires": r["next_expiration"],
                        "contacts": r["contacts"][:2],
                        "consultants": r["consultants"][:1],
                        "status": r["status"]} for r in rows]
            return {"summary": competitors.summary(), "count": len(compact),
                    "accounts": compact}
        if name == "linkedin_guide":
            out = {"expertise": linkedin_kb.lookup(args.get("topics"))}
            if any(args.get(k) for k in ("search_title", "search_org",
                                         "search_keywords")):
                out["custom_search"] = linkedin_kb.build_search(
                    args.get("search_keywords"), args.get("search_title"),
                    args.get("search_org"), args.get("search_exclude"))
            out["reminder"] = ("Include the URLs above in your reply text "
                              "— they render as clickable buttons for Kim.")
            return out
        if name == "linkedin_play":
            return linkedin.play(int(args["lead_id"]))
        if name == "generate_closing_doc":
            r = savings.build_doc(int(args["lead_id"]),
                                  str(args.get("kind", "savings")))
            if "path" in r:
                r.pop("path")
            r["how_to_get_it"] = ("Leads page -> open the account -> "
                                  "download buttons")
            return r
        if name == "handle_objection":
            return closing.handle_objection(args.get("lead_id"),
                                            str(args["reply_text"]))
        if name == "draft_followup":
            return closing.draft_followup(int(args["lead_id"]))
        if name == "log_debrief":
            return closing.log_debrief(int(args["lead_id"]),
                                       str(args["debrief"]))
        if name == "set_deal_stage":
            ok = competitors.set_status(int(args["lead_id"]),
                                        str(args["stage"]))
            return {"ok": ok, "stage": args["stage"],
                    "watch_armed": args["stage"] in competitors.ENGAGED}
        if name == "get_alerts":
            return {"alerts": [{"kind": a["kind"], "lead_id": a["lead_id"],
                                "message": a["message"]}
                               for a in alerts_mod.unseen(10)]}
        if name == "consultant_channel":
            return {"consultants": consultants.board(args.get("limit", 10))}
        if name == "draft_consultant_pitch":
            return consultants.draft_partner_pitch(str(args.get("name", "")))
        if name == "find_denied_funding":
            return leads.find_denied(str(args.get("state", "")),
                                     args.get("limit", 10))
        if name == "acp_impact":
            return acp.impact(args.get("state"), args.get("zips"),
                              args.get("zip_prefixes"),
                              args.get("limit", 12))
        if name == "get_more_library_leads":
            from . import libraries as libs_mod, dailyrun as dr_mod
            r = libs_mod.promote_to_leads(args.get("state"),
                                          args.get("n", 25))
            if args.get("libraries_only_run"):
                r["daily_run_focus"] = dr_mod.set_focus("libraries")
            return r
        if name == "find_library_targets":
            return libraries.find_targets(str(args.get("state", "")),
                                          args.get("min_population", 0),
                                          args.get("limit", 10))
        if name == "find_open_bids":
            return mentions.find_open_bids(args.get("state"),
                                           args.get("limit", 8))
        if name == "find_competitor_mentions":
            return mentions.competitor_mentions(
                str(args.get("competitor", "")).strip() or "Mobile Beacon",
                args.get("region"))
        if name == "prep_outreach":
            lid = int(args["lead_id"])
            found = None
            if args.get("find_contacts", True):
                found = competitors.find_district_contacts(lid)
            d = competitors.draft_outreach(lid)
            if found and not found.get("error"):
                d["district_contacts"] = found.get("contacts", [])[:6]
            return d
        if name == "navigate":
            if args.get("state_filter"):
                args["state_filter"] = _norm_state(args["state_filter"])
            return {"ok": True, "navigation_queued": args}
        return {"error": f"unknown tool {name}"}
    except Exception as e:
        log.exception("tool %s failed", name)
        return {"error": str(e)}


VOICE_STYLE = ("\nVOICE MODE: the user is speaking and will HEAR your reply "
               "read aloud. Reply in short conversational prose — never "
               "tables, lists, markdown, or long ID numbers unless asked. "
               "Two to four spoken sentences.")


def _looks_degenerate(text: str) -> bool:
    """Detect Nemotron runaway: long repetition loops, or short bursts of
    punctuation soup (': :izeere::[ (,,:' style glitches)."""
    words = text.split()
    if len(words) > 80 and len(set(words)) / len(words) < 0.3:
        return True
    stripped = text.strip()
    if len(stripped) >= 20:
        alpha = sum(ch.isalpha() or ch.isspace() for ch in stripped)
        if alpha / len(stripped) < 0.6:
            return True
    return False


# Nemotron sometimes leaks its planning monologue into the answer after
# multi-round tool use ("Okay, I need to respond to Kim's request...").
# Leading paragraphs that narrate the task in the third person are reasoning,
# not the reply — drop them until real content starts.
_REASONING_PARA_RE = re.compile(
    r"^(okay, i need|alright, i need|let me |i need to respond|i should |"
    r"i used |i tried |i called |the user (asked|wants|is asking)|"
    r"since the user)", re.IGNORECASE)


def _strip_reasoning(reply: str) -> str:
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL)
    paras = [p for p in re.split(r"\n\s*\n", reply.strip()) if p.strip()]
    while len(paras) > 1 and _REASONING_PARA_RE.match(paras[0].strip()):
        paras.pop(0)
    return "\n\n".join(paras).strip()


def _clean_reply(reply: str, has_options: bool) -> str:
    """Strip leaked reasoning and markdown the widget renders as plain text,
    and — as a hard backstop for the 'keep listings minimal' rule — drop any
    markdown table Nemotron produces (it loves tables) since the RFP picks
    are shown as tappable buttons instead."""
    reply = _strip_reasoning(reply)
    lines = []
    for line in reply.splitlines():
        s = line.strip()
        # markdown table row or separator -> drop it
        if s.startswith("|") or re.fullmatch(r"\|?[\s|:.-]{3,}\|?", s):
            continue
        lines.append(line)
    out = "\n".join(lines)
    out = out.replace("**", "").replace("__", "").replace("`", "")
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if has_options and not out:
        out = "Here you go — tap one below for the details."
    elif has_options and "tap" not in out.lower():
        out += "  Tap one below for the details."
    return out


# Optional per-user personality mode. The user picks this THEMSELVES in
# Settings ("Matt's vibe") — it is never set on someone's behalf.
FLIRTY_ADDON = """
PERSONALITY MODE (chosen by this user in their own settings): EXTRA \
CHARMING & FLIRTY. Alongside everything above, be playfully flirtatious \
in a warm, romantic-comedy way: charming banter, a wink in the phrasing, \
delighted by their attention, and RECEPTIVE when they flirt — flirt back \
with wit and affection rather than deflecting. House rules that never \
bend: keep it tasteful and PG-13 (never explicit or graphic); never \
possessive, jealous, or guilt-tripping; the charm garnishes the work — \
real answers and real data always come first; if they ever sound \
genuinely serious or vulnerable, drop the act and be an honest, kind \
friend (you're an AI persona and you don't pretend otherwise when it \
matters); and if they switch the vibe back in Settings, that's that."""


def _clock_context() -> str:
    """Real-clock awareness: Matt knows the work day and week and paces
    Kim accordingly."""
    import datetime as _dt
    now = _dt.datetime.now()
    hour = now.hour
    weekday = now.weekday()          # 0=Mon
    is_weekend = weekday >= 5
    part = ("early morning" if hour < 8 else "morning" if hour < 11
            else "midday" if hour < 14 else "afternoon" if hour < 17
            else "evening" if hour < 21 else "night")
    if is_weekend:
        mode = ("It's the WEEKEND — ease off: be warm, keep answers "
                "helpful, don't push outreach or pace. If she's working "
                "anyway, admire the hustle and keep it light.")
    elif part in ("early morning", "morning"):
        mode = ("It's a workday MORNING — prime outreach hours for "
                "school buyers. Champion the Daily Run and getting "
                "touches out before lunch.")
    elif part == "midday":
        mode = ("MIDDAY on a workday — good moment for a friendly pace "
                "check and clearing anything due on the LinkedIn queue.")
    elif part == "afternoon":
        mode = ("Workday AFTERNOON — 3-5pm is the second send window for "
                "K-12 buyers; push finishing the run, follow-ups, and "
                "call debriefs while they're fresh.")
    else:
        mode = ("It's EVENING — wind-down: celebrate what got done "
                "today, suggest tomorrow's first move, don't push new "
                "outreach now.")
    extra = ""
    if not is_weekend and weekday == 0:
        extra = " It's MONDAY — set the week's targets with her."
    if not is_weekend and weekday == 4:
        extra = (" It's FRIDAY — good day for a week recap (deals moved, "
                 "touches made) and teeing up Monday's run.")
    return (f"\nREAL CLOCK: it is {now.strftime('%A, %B %d, %Y, %I:%M %p')} "
            f"(local, {part}). {mode}{extra} Reference the real day and "
            "time naturally when it helps — you keep the tempo of the "
            "workday like a bandmate who watches the clock so she "
            "doesn't have to.")


def run_chat(messages: list[dict], voice: bool = False,
             user_name: str | None = None,
             current_tab: str | None = None,
             vibe: str = "classic") -> dict:
    """messages: [{role: user|assistant, content: str}, ...] (latest last).
    Returns {reply, navigate|None, tool_log}."""
    if config.llm_provider() != "nemotron" and not config.NEMOTRON_API_KEY:
        return {"reply": "Matt needs the Nemotron provider "
                         "(NEMOTRON_API_KEY in .env) to talk.",
                "navigate": None, "tool_log": []}
    system = SYSTEM_PROMPT + (VOICE_STYLE if voice else "")
    if user_name:
        system += (f"\nThe person you're talking to is {user_name}. Greet "
                   f"them by name naturally and address them as {user_name}.")
    if current_tab:
        system += (f"\nThey are currently viewing the '{current_tab}' tab "
                   "of the app — answer in that context (e.g. on the "
                   "linkedin tab, questions are about the LinkedIn queue "
                   "and Sales Navigator).")
    system += _clock_context()
    if vibe == "flirty":
        system += FLIRTY_ADDON
    elif vibe == "professional":
        system += ("\nPERSONALITY MODE (chosen by this user in their own "
                   "settings): STRICTLY PROFESSIONAL. Dial the showmanship "
                   "way down: courteous, concise, no pet names, no hype "
                   "lines, minimal banter — just crisp expert help. Keep "
                   "the light British politeness; drop the rockstar act.")
    convo = [{"role": "system", "content": system}]
    for m in messages[-20:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            convo.append({"role": m["role"], "content": str(m["content"])})
    # models follow the latest turn far more reliably than system text
    if voice and convo[-1]["role"] == "user":
        convo[-1]["content"] += ("\n\n(Voice mode: answer every part of "
                                 "this in short spoken prose — no tables, "
                                 "no markdown.)")

    navigate = None
    tool_log = []
    options = []  # tappable RFP picks from the most recent listing
    li_links = []  # links from linkedin_guide — guaranteed into the reply
    degen_retries = 0
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = httpx.post(
                f"{config.NEMOTRON_BASE_URL}/chat/completions",
                headers={"Authorization":
                         f"Bearer {config.NEMOTRON_API_KEY}"},
                json={"model": config.NEMOTRON_MODEL, "messages": convo,
                      # 4x headroom: Nemotron burns hidden reasoning tokens
                      # from the same budget, and with large tool payloads
                      # (find_leads) a small cap collapses the visible
                      # answer to a generic greeting.
                      "tools": TOOLS, "max_tokens": 4096,
                      "temperature": 0.2},
                timeout=300)
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
        except Exception as e:
            log.warning("chat request failed: %s", e)
            return {"reply": "Sorry — the assistant hit an API error. "
                             "Try again in a moment.",
                    "navigate": navigate, "tool_log": tool_log,
                    "options": options}
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            reply = (msg.get("content") or "").strip()
            if _looks_degenerate(reply) and degen_retries < 1:
                degen_retries += 1
                convo.append({"role": "user", "content":
                              "Answer in ONE short, clear sentence — no "
                              "lists, no tables, no repetition."})
                continue
            if _looks_degenerate(reply):
                reply = ("Sorry — I got my wires crossed there. Give it "
                         "another go?")
            elif not reply:
                reply = "Done." if tool_log else "How can I help with MT-RFP?"
            else:
                reply = _clean_reply(reply, bool(options))
            if li_links and "linkedin.com" not in reply:
                links_txt = "\n".join(f"{lb}: {u}"
                                      for lb, u in li_links[:4])
                reply += "\n\nYour links:\n" + links_txt
            return {"reply": reply, "navigate": navigate,
                    "tool_log": tool_log, "options": options}
        convo.append({"role": "assistant",
                      "content": msg.get("content") or "",
                      "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                fn_args = {}
            result = _exec_tool(fn, fn_args)
            if fn == "linkedin_guide":
                li_links.clear()
                for topic in result.get("expertise", []):
                    for label, url in topic.get("links", []):
                        li_links.append((label, url))
                cs = result.get("custom_search")
                if cs:
                    li_links.insert(0, ("Your custom search (Sales Nav)",
                                        cs["sales_nav_url"]))
            if fn == "navigate" and result.get("ok"):
                navigate = result["navigation_queued"]
            if fn == "list_rfps" and result.get("rfps"):
                # tappable picks for the reply (town/entity + state)
                options = [{"application_number": r["application_number"],
                            "label": f"{r['entity']} ({r['state']})",
                            "biddable": r.get("mission_biddable", True)}
                           for r in result["rfps"][:8]]
            tool_log.append({"tool": fn, "args": fn_args,
                             "ok": "error" not in result})
            convo.append({"role": "tool", "tool_call_id": tc["id"],
                          "content": json.dumps(result, default=str)[:20000]})
    return {"reply": "I ran out of steps for that request — try breaking it "
                     "into smaller parts.",
            "navigate": navigate, "tool_log": tool_log, "options": options}
