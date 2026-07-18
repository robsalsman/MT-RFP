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

import httpx

from . import ai, config, db, respond, scoring
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


SYSTEM_PROMPT = """/no_think You are the MT-RFP Assistant, embedded in \
Mission Telecom's RFP intelligence platform. You are a full expert on the \
app, the E-Rate domain, AND Mission Telecom itself (the company, its \
services, pricing, programs, and website). Be concise and helpful; use \
tools to answer with real data instead of guessing, and use the navigate \
tool to take the user to the right place in the app.

ABOUT MISSION TELECOM (the company; call get_company_info for full details, \
exact pricing, team, programs, and page URLs)
- Nonprofit telecom carrier providing affordable wireless broadband and \
phone service — up to 70% off market rates — to schools, libraries, \
nonprofits, and government/social welfare agencies. Runs exclusively on the \
T-Mobile 5G/4G network. HQ: 8310 S Valley Hwy Ste 300, Englewood, CO 80112; \
877-641-9444; info@missiontelecom.org; website missiontelecom.org.
- Offerings: phone plans (Amplify Essential $15/line/mo 10GB, Amplify \
Unlimited $30/line/mo with 5-year price guarantee), broadband/hotspot & \
fixed wireless plans ($20-25/mo), connected devices (hotspots, tablets), \
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
how well the RFP matches Mission Telecom's wireless-connectivity catalog; \
Deal size (20) — log-scaled prior-FY 471 spend; Winnability (20) — bid \
barriers, remaining window, restrictions; Strategic fit (20) — entity type \
(libraries and schools rank highest), wireless demand, priority states.
- MISSION FIT: scoring is tuned to Mission Telecom's real business — a \
nonprofit WIRELESS ISP on the T-Mobile network. "Biddable" RFPs are E-Rate \
Category 1 internet access / data transmission a wireless carrier can serve. \
RFPs requiring leased fiber, or that are only Category 2 internal-connections \
hardware (switches, routers, firewalls, access points, cabling), are marked \
NOT a fit and scored far lower — Mission Telecom sells connectivity, not \
fiber builds or LAN equipment. The dashboard defaults to Mission-fit-only.

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
        "name": "navigate",
        "description": "Move the user's UI: switch page, apply dashboard "
                       "filters, and/or open an RFP's detail drawer.",
        "parameters": {"type": "object", "properties": {
            "tab": {"type": "string",
                    "enum": ["dashboard", "uploads", "settings"]},
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


def run_chat(messages: list[dict], voice: bool = False) -> dict:
    """messages: [{role: user|assistant, content: str}, ...] (latest last).
    Returns {reply, navigate|None, tool_log}."""
    if config.llm_provider() != "nemotron" and not config.NEMOTRON_API_KEY:
        return {"reply": "The assistant needs the Nemotron provider "
                         "(NEMOTRON_API_KEY in .env).",
                "navigate": None, "tool_log": []}
    system = SYSTEM_PROMPT + (VOICE_STYLE if voice else "")
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
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = httpx.post(
                f"{config.NEMOTRON_BASE_URL}/chat/completions",
                headers={"Authorization":
                         f"Bearer {config.NEMOTRON_API_KEY}"},
                json={"model": config.NEMOTRON_MODEL, "messages": convo,
                      "tools": TOOLS, "max_tokens": 4000,
                      "temperature": 0.2},
                timeout=300)
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
        except Exception as e:
            log.warning("chat request failed: %s", e)
            return {"reply": "Sorry — the assistant hit an API error. "
                             "Try again in a moment.",
                    "navigate": navigate, "tool_log": tool_log}
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            reply = (msg.get("content") or "").strip()
            if not reply:
                reply = "Done." if tool_log else "How can I help with MT-RFP?"
            # the widget renders plain text; drop markdown emphasis
            reply = reply.replace("**", "").replace("__", "")
            return {"reply": reply, "navigate": navigate,
                    "tool_log": tool_log}
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
            if fn == "navigate" and result.get("ok"):
                navigate = result["navigation_queued"]
            tool_log.append({"tool": fn, "args": fn_args,
                             "ok": "error" not in result})
            convo.append({"role": "tool", "tool_call_id": tc["id"],
                          "content": json.dumps(result, default=str)[:20000]})
    return {"reply": "I ran out of steps for that request — try breaking it "
                     "into smaller parts.",
            "navigate": navigate, "tool_log": tool_log}
