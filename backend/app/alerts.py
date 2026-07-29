"""Closing alerts: the signals that move deals.

- 470-WATCH: every engaged lead's BEN is watched for a NEW Form 470
  posting on USAC — the moment a district Kim is talking to legally
  enters the market. That's the buying signal; Matt announces it.
- STALE-DEAL NUDGES: engaged deals that have gone quiet past their
  stage's threshold (quote sitting 7 days, reply unanswered 4 days...)
  get resurfaced so silence never kills a deal.

Checks run at most every 30 minutes, computed when the app is asked for
alerts (no background scheduler needed); results dedupe into the alerts
table so each event fires exactly once.
"""
import datetime
import json
import logging
import time

from . import competitors, config, db, soda

log = logging.getLogger(__name__)

CHECK_EVERY_S = 30 * 60


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(timespec="seconds")


def _add(conn, kind: str, lead_id: int | None, message: str,
         dedupe_key: str) -> bool:
    try:
        conn.execute(
            "INSERT INTO alerts (kind, lead_id, message, created_at, "
            "dedupe_key) VALUES (?,?,?,?,?)",
            (kind, lead_id, message, _now(), dedupe_key))
        return True
    except Exception:   # duplicate dedupe_key -> already alerted
        return False


def run_checks(force: bool = False) -> int:
    """Throttled; returns number of NEW alerts created."""
    with db.closing_conn() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key="
                           "'alerts_last_run'").fetchone()
        last = json.loads(row["value"]) if row else 0
        if not force and time.time() - last < CHECK_EVERY_S:
            return 0
        conn.execute("INSERT OR REPLACE INTO kv (key, value) VALUES "
                     "('alerts_last_run', ?)", (json.dumps(time.time()),))
        conn.commit()
    created = _check_stale()
    try:
        created += _check_470_watch()
    except Exception as e:   # offline is fine — stale checks still ran
        log.warning("470-watch check failed: %s", e)
    return created


def _check_stale() -> int:
    created = 0
    today = datetime.datetime.utcnow()
    with db.closing_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, org, state, status, stage_date FROM "
            "competitor_leads WHERE status IN ({})".format(
                ",".join("?" * len(competitors.STALE_AFTER))),
            tuple(competitors.STALE_AFTER))]
        for r in rows:
            if not r["stage_date"]:
                continue
            try:
                since = (today - datetime.datetime.fromisoformat(
                    r["stage_date"])).days
            except ValueError:
                continue
            limit = competitors.STALE_AFTER[r["status"]]
            if since >= limit:
                msg = (f"{r['org']} ({r['state']}) has sat in "
                       f"'{r['status']}' for {since} days — time for a "
                       "follow-up nudge?")
                # dedupe per stage-entry so re-staging re-arms the alert
                key = f"stale:{r['id']}:{r['status']}:{r['stage_date']}"
                if _add(conn, "stale", r["id"], msg, key):
                    created += 1
        conn.commit()
    return created


def _check_470_watch() -> int:
    """Any watched BEN with a Form 470 certified in the last 45 days."""
    with db.closing_conn() as conn:
        watched = {str(r["ben"]): dict(r) for r in conn.execute(
            "SELECT id, ben, org, state FROM competitor_leads "
            "WHERE watch=1")}
    if not watched:
        return 0
    since = (datetime.date.today()
             - datetime.timedelta(days=45)).strftime("%Y-%m-%dT00:00:00")
    bens = sorted(watched)
    created = 0
    for i in range(0, len(bens), 80):
        chunk = bens[i:i + 80]
        blist = ",".join(f"'{b}'" for b in chunk)
        rows = soda.fetch_all(
            config.DATASET_FORM470,
            where=(f"billed_entity_number in({blist}) AND "
                   f"certified_date_time > '{since}'"),
            select="application_number, billed_entity_number, "
                   "certified_date_time", order="application_number",
            use_cache=False)
        with db.closing_conn() as conn:
            for r in rows:
                ben = str(r.get("billed_entity_number") or "")
                lead = watched.get(ben)
                an = r.get("application_number")
                if not lead or not an:
                    continue
                cert = (r.get("certified_date_time") or "")[:10]
                msg = (f"BUYING SIGNAL: {lead['org']} ({lead['state']}) "
                       f"posted Form 470 #{an} on {cert} — their 28-day "
                       "bidding window is open NOW. Want the bid drafted?")
                if _add(conn, "form470", lead["id"], msg, f"470:{an}"):
                    created += 1
            conn.commit()
    return created


def unseen(limit: int = 10) -> list[dict]:
    run_checks()
    with db.closing_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM alerts WHERE seen=0 ORDER BY "
            "CASE kind WHEN 'form470' THEN 0 ELSE 1 END, id DESC LIMIT ?",
            (limit,))]
    return rows


def mark_seen(ids: list[int]) -> int:
    if not ids:
        return 0
    with db.closing_conn() as conn:
        cur = conn.execute(
            "UPDATE alerts SET seen=1 WHERE id IN ({})".format(
                ",".join("?" * len(ids))), tuple(int(i) for i in ids))
        conn.commit()
        return cur.rowcount
