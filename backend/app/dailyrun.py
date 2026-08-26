"""The Daily Run: Matt pre-works the leads so Kim only decides.

Each run picks the best ~20 workable leads and pre-computes everything
slow — district contacts (website crawl) and the outreach draft — so the
review UI is instant. Ordering enforces warm-before-cold: leads with a
reply always jump ahead of new outreach. Leads with no reachable human
(consultant-only contact) are auto-routed to the consultant channel
instead of wasting a slot.

A fixed share of each run goes to greenfield library leads (LIBRARY_SHARE)
— they have no incumbent spend to score against, so left to the numbers
alone they never appear. Changing the focus refills today's run instead of
waiting for tomorrow's.

Runs build lazily in the background the first time anyone asks for
today's run (the laptop hosts the app, so "overnight" = "before Kim
looks"), and can be rebuilt on demand.
"""
import datetime
import json
import logging
import threading
import time

from . import closing, competitors, db

log = logging.getLogger(__name__)

_SCHEMA = """CREATE TABLE IF NOT EXISTS daily_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    lead_id INTEGER NOT NULL,
    position INTEGER,
    kind TEXT,                -- 'warm' (they replied) | 'cold'
    state TEXT DEFAULT 'pending',   -- pending | sent | skipped
    UNIQUE(run_date, lead_id)
);"""

BUILD_FLAG = "daily_run_building"
DEFAULT_N = 20
# Share of a mixed run's cold slots that goes to libraries. A library is
# scored off its own budget and a district off the money it already pays a
# competitor — two different scales, so leaving the split to the score gives
# an all-schools run or an all-libraries one depending on whose numbers are
# bigger that week. Kim gets a fixed share of each instead; libraries-only
# is the focus setting, not an accident of scoring.
LIBRARY_SHARE = 0.34


def _ensure():
    with db.closing_conn() as conn:
        conn.execute(_SCHEMA)
        conn.commit()


def _today() -> str:
    return datetime.date.today().isoformat()


def get_focus() -> str:
    with db.closing_conn() as conn:
        f = db.kv_get(conn, "daily_run_focus", "all")
    return f if f in ("all", "libraries") else "all"


def set_focus(focus: str, rebuild: bool = True) -> str:
    """Change what the run pulls from. Today's run was already assembled
    under the old focus, so a change has to invalidate it — otherwise Kim
    flips to libraries-only and stares at yesterday's schools all day.
    Her sent/skipped decisions are kept; only the untouched slots are
    refilled, in the background."""
    f = focus if focus in ("all", "libraries") else "all"
    with db.closing_conn() as conn:
        prev = db.kv_get(conn, "daily_run_focus", "all")
        db.kv_set(conn, "daily_run_focus", f)
        conn.commit()
    if rebuild and f != prev:
        _ensure()
        with db.closing_conn() as conn:
            conn.execute("DELETE FROM daily_run WHERE run_date=? AND "
                         "state='pending'", (_today(),))
            conn.commit()
        refill_bg()
    return f


def _safe_build():
    try:
        build()
    except Exception:
        log.exception("daily-run refill failed")


def refill_bg() -> bool:
    """Fire-and-forget refill of today's run (build crawls and drafts, so
    it must never block the request that changed the focus)."""
    if is_building():
        return False
    threading.Thread(target=_safe_build, daemon=True).start()
    return True


def _is_library(lead: dict) -> bool:
    return ("ibrar" in (lead.get("entity_type") or "").lower()
            or "librar" in (lead.get("org") or "").lower()
            or lead.get("competitor") == "greenfield")


def _score(lead: dict) -> float:
    return _apply_prefs(lead, _base_score(lead))


def _apply_prefs(lead: dict, s: float) -> float:
    """Kim's live hunting prefs (vault) re-rank the run without a deploy."""
    try:
        from . import vault
        prefs = vault.get_prefs()
        if (lead.get("state") or "").upper() in prefs["priority_states"]:
            s *= 1.6
        org = (lead.get("org") or "").lower()
        if any(t in org for t in prefs["avoid_terms"]):
            s *= 0.05
    except Exception:
        pass
    return s


def _base_score(lead: dict) -> float:
    if lead.get("competitor") == "greenfield":
        # no incumbent spend - rank by need and budget
        s = float(lead.get("budget") or 0) * 0.02
        try:
            from . import acp
            hh = acp.households_for_zip(lead.get("zip")) or 0
            s += hh * 40
        except Exception:
            pass
        return s
    s = float(lead.get("spend") or 0)
    if lead.get("source") == "ecf":
        s *= 0.6
    exp = lead.get("next_expiration")
    if exp:
        today = _today()
        horizon = (datetime.date.today()
                   + datetime.timedelta(days=456)).isoformat()
        if today <= exp <= horizon:
            s *= 1.5
    return s


def _reachable(lead: dict) -> bool:
    """A run slot needs a human Kim can actually email."""
    if any(c.get("email") for c in lead.get("extra_contacts", [])):
        return True
    if competitors.district_domain(lead):
        return True
    return False


def build(n: int = DEFAULT_N, force: bool = False) -> dict:
    """Assemble today's run. Slow (crawls + drafts) — call in background."""
    _ensure()
    today = _today()
    with db.closing_conn() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM daily_run WHERE run_date=? AND "
            "state='pending'", (today,)).fetchone()[0]
        if existing and not force:
            return {"already_built": True}
        if force:
            conn.execute("DELETE FROM daily_run WHERE run_date=?", (today,))
            conn.commit()
        db.kv_set(conn, BUILD_FLAG, time.time())
        conn.commit()
    try:
        return _build_inner(n, today)
    finally:
        with db.closing_conn() as conn:
            db.kv_set(conn, BUILD_FLAG, 0)
            conn.commit()


def _build_inner(n: int, today: str) -> dict:
    # leads Kim already acted on today keep their slot: a refill after a
    # focus change must neither re-serve nor lose them
    with db.closing_conn() as conn:
        kept = {r[0] for r in conn.execute(
            "SELECT lead_id FROM daily_run WHERE run_date=?", (today,))}
    # candidates: warm replies first, then fresh leads by score
    warm = competitors.list_leads(status="replied", sort="spend", limit=50)
    cold = competitors.list_leads(status="new", sort="spend", limit=300)
    # Greenfield libraries carry no incumbent spend, so a spend-sorted page
    # never reaches them however deep it goes. Pull that pool in explicitly
    # and let _score rank them against the paying accounts — otherwise the
    # run is schools-only no matter how many libraries are on the board.
    green = competitors.list_leads(competitor=competitors.GREENFIELD,
                                   status="new", limit=300)
    green_warm = competitors.list_leads(competitor=competitors.GREENFIELD,
                                        status="replied", limit=50)
    seen = {l["id"] for l in cold}
    cold += [l for l in green if l["id"] not in seen]
    seen_warm = {l["id"] for l in warm}
    warm += [l for l in green_warm if l["id"] not in seen_warm]
    focus = get_focus()
    if focus == "libraries":
        cold = [l for l in cold if _is_library(l)]
        warm = [l for l in warm if _is_library(l)]
    warm = [l for l in warm if l["id"] not in kept]
    cold = [l for l in cold if l["id"] not in kept]
    cold.sort(key=_score, reverse=True)

    slots = max(0, n - len(kept))
    picked: list[tuple[dict, str]] = [(l, "warm") for l in warm[:8]][:slots]
    consultant_routed: dict[str, int] = {}

    def take(pool: list[dict], want: int) -> None:
        """Fill up to `want` slots from `pool`, routing the leads with no
        reachable human to their consultant instead of burning a slot."""
        while pool and want > 0 and len(picked) < slots:
            lead = pool.pop(0)
            if not _reachable(lead):
                cons = (lead.get("consultants")
                        or ["(no consultant listed)"])[0]
                name = cons.split("<")[0].strip()
                consultant_routed[name] = consultant_routed.get(name, 0) + 1
                continue
            picked.append((lead, "cold"))
            want -= 1

    libs = [l for l in cold if _is_library(l)]
    others = [l for l in cold if not _is_library(l)]
    if focus == "libraries":
        take(libs, slots)
    else:
        take(libs, round((slots - len(picked)) * LIBRARY_SHARE))
        take(others, slots)
        take(libs, slots)   # short on districts: don't run light

    prepped = 0
    for lead, kind in picked:
        lid = lead["id"]
        try:
            # contacts: crawl once if we have a domain but no named people
            if not lead.get("extra_contacts") \
                    and competitors.district_domain(lead):
                competitors.find_district_contacts(lid)
            # draft: warm leads get a stage-aware follow-up, cold leads the
            # standard outreach; both persist on the lead
            if kind == "warm":
                d = closing.draft_followup(lid)
                if d.get("draft"):
                    with db.closing_conn() as conn:
                        conn.execute("UPDATE competitor_leads SET "
                                     "email_draft=? WHERE id=?",
                                     (d["draft"], lid))
                        conn.commit()
            elif not lead.get("email_draft"):
                competitors.draft_outreach(lid)
            prepped += 1
        except Exception as e:
            log.warning("daily-run prep failed for lead %s: %s", lid, e)
    with db.closing_conn() as conn:
        for i, (lead, kind) in enumerate(picked, start=len(kept)):
            conn.execute(
                "INSERT OR IGNORE INTO daily_run (run_date, lead_id, "
                "position, kind) VALUES (?,?,?,?)",
                (today, lead["id"], i, kind))
        db.kv_set(conn, "daily_run_consultant_routed",
                  {"date": today, "routes": consultant_routed})
        conn.commit()
    log.info("daily run built: %d items (%d prepped), %d consultant-routed",
             len(picked), prepped, sum(consultant_routed.values()))
    try:
        from . import vault
        vault.journal(f"daily run built: {len(picked)} leads "
                      f"({sum(1 for _, k in picked if k == 'warm')} warm), "
                      f"{sum(consultant_routed.values())} consultant-routed")
    except Exception:
        pass
    return {"built": len(picked), "prepped": prepped,
            "consultant_routed": consultant_routed}


def is_building() -> bool:
    with db.closing_conn() as conn:
        t = db.kv_get(conn, BUILD_FLAG, 0) or 0
    return bool(t) and time.time() - t < 45 * 60


def get_run() -> dict:
    """Today's run with full lead payloads, pending first."""
    _ensure()
    today = _today()
    with db.closing_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM daily_run WHERE run_date=? ORDER BY "
            "CASE state WHEN 'pending' THEN 0 ELSE 1 END, position",
            (today,))]
        routed = db.kv_get(conn, "daily_run_consultant_routed", {}) or {}
    items = []
    for r in rows:
        lead = competitors.get_lead(r["lead_id"])
        if not lead:
            continue
        best = competitors._best_contact(lead)
        items.append({
            "lead_id": lead["id"], "kind": r["kind"], "state": r["state"],
            "org": lead["org"], "state_code": lead["state"],
            "competitor": lead["competitor_label"],
            "spend": lead["spend"], "source": lead["source"],
            "devices": lead.get("devices"),
            "expires": lead.get("next_expiration"),
            "stage": lead.get("status"),
            "to_name": best.get("name"), "to_email": best.get("email"),
            "draft": lead.get("email_draft") or "",
            "notes": (lead.get("notes") or [])[-1:],
        })
    done = sum(1 for i in items if i["state"] != "pending")
    return {"date": today, "exists": bool(rows),
            "building": is_building(),
            "total": len(items), "done": done,
            "consultant_routed": routed.get("routes", {})
            if routed.get("date") == today else {},
            "items": items,
            "pace": _pace()}


def act(lead_id: int, action: str) -> dict:
    """Kim decided: sent -> log + advance stage; skipped -> next."""
    if action not in ("sent", "skipped"):
        return {"error": "action must be sent|skipped"}
    _ensure()
    today = _today()
    with db.closing_conn() as conn:
        cur = conn.execute(
            "UPDATE daily_run SET state=? WHERE run_date=? AND lead_id=?",
            (action, today, lead_id))
        conn.commit()
        if not cur.rowcount:
            return {"error": "lead not in today's run"}
    lead = competitors.get_lead(lead_id)
    if action == "sent":
        competitors.add_note(lead_id, "Daily run: outreach email sent")
        if lead and lead.get("status") == "new":
            competitors.set_status(lead_id, "contacted")
    try:
        from . import vault
        if lead:
            vault.journal(f"run: Kim {action} {lead['org']} "
                          f"({lead.get('state')})")
            if action == "sent":
                vault.account_event(lead["org"], "Kim sent outreach "
                                    "(daily run)")
    except Exception:
        pass
    return {"ok": True, "action": action}


def _pace() -> dict:
    """Touches this month + a projected finish line for untouched leads."""
    first = datetime.date.today().replace(day=1).isoformat()
    with db.closing_conn() as conn:
        touched = conn.execute(
            "SELECT COUNT(*) FROM competitor_leads WHERE stage_date >= ? "
            "AND status NOT IN ('new','dismissed')", (first,)).fetchone()[0]
        remaining = conn.execute(
            "SELECT COUNT(*) FROM competitor_leads WHERE status='new'"
        ).fetchone()[0]
    day = max(1, datetime.date.today().day)
    per_day = touched / day
    days_left = round(remaining / per_day) if per_day > 0 else None
    return {"touched_this_month": touched, "untouched_leads": remaining,
            "per_day": round(per_day, 1),
            "days_to_clear_board": days_left}
