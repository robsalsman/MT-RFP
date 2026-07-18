"""MT-RFP API server.

Endpoints power the React dashboard: RFP list/detail, manual + scheduled
sync, price-list and company-profile management, response generation, and
settings. All USAC access is read-only; nothing is ever auto-submitted.
"""
import asyncio
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import ai, config, db, ingest, keepawake, respond, status as status_mod
from . import pricing as pricing_mod

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("mtrfp")

app = FastAPI(title="MT-RFP", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_sync_lock = threading.Lock()
_sync_state = {"running": False, "last_result": None, "last_error": None}


# ---------------------------------------------------------------------------
# Lifecycle + scheduler
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    db.init_db()
    asyncio.create_task(_scheduler_loop())


async def _scheduler_loop():
    interval = config.SYNC_INTERVAL_HOURS * 3600
    while True:
        try:
            await asyncio.to_thread(_run_sync_guarded)
        except Exception:
            log.exception("scheduled sync failed")
        await asyncio.sleep(interval)


def _run_sync_guarded():
    if not _sync_lock.acquire(blocking=False):
        return  # a sync is already running
    _sync_state.update(running=True, last_error=None)
    try:
        with keepawake.hold("sync"):  # don't let the box sleep mid-sync
            result = ingest.run_sync()
            analyzed = ai.analyze_open_batch()
            result["analyzed"] = analyzed
            _sync_state["last_result"] = result
    except Exception as e:
        _sync_state["last_error"] = str(e)
        raise
    finally:
        _sync_state["running"] = False
        _sync_lock.release()


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

@app.post("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks):
    if _sync_state["running"]:
        return {"started": False, "reason": "sync already running"}
    background_tasks.add_task(_run_sync_guarded)
    return {"started": True}


@app.get("/api/sync/status")
def sync_status():
    with db.closing_conn() as conn:
        last = conn.execute(
            "SELECT * FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
    return {"running": _sync_state["running"],
            "last_error": _sync_state["last_error"],
            "last_sync": dict(last) if last else None}


# ---------------------------------------------------------------------------
# RFP list / detail
# ---------------------------------------------------------------------------

def _decorate(row: dict) -> dict:
    certified = status_mod.parse_usac_date(row.get("certified_date"))
    acd = status_mod.parse_usac_date(row.get("allowable_contract_date"))
    st, days_left = status_mod.compute_status(certified, acd)
    close = status_mod.allowable_contract_date(certified, acd)
    out = dict(row)
    out["status"] = st
    out["days_left"] = days_left
    out["bid_deadline"] = close.isoformat() if close else None
    if close:
        eastern_dt = datetime(close.year, close.month, close.day,
                              tzinfo=ZoneInfo(config.EASTERN_TZ))
        out["bid_deadline_eastern"] = eastern_dt.strftime(
            "%Y-%m-%d 23:59 %Z")
    for f in ("service_types", "functions", "rfp_doc_urls", "doc_files",
              "mission_blockers"):
        try:
            out[f] = json.loads(out.get(f) or "[]")
        except (TypeError, json.JSONDecodeError):
            out[f] = []
    for f in ("score_breakdown", "analysis"):
        try:
            out[f] = json.loads(out.get(f)) if out.get(f) else None
        except (TypeError, json.JSONDecodeError):
            out[f] = None
    return out


@app.get("/api/rfps")
def list_rfps(status: str | None = None, state: str | None = None,
              applicant_type: str | None = None, mission_only: bool = False,
              relevant_only: bool = True, q: str | None = None):
    sql = "SELECT * FROM rfps"
    clauses, params = [], []
    if relevant_only:
        clauses.append("relevant=1")
    if mission_only:
        clauses.append("mission_biddable=1")
    if state:
        clauses.append("state=?")
        params.append(state.upper())
    if applicant_type:
        clauses.append("applicant_type=?")
        params.append(applicant_type)
    if q:
        clauses.append("(billed_entity_name LIKE ? OR application_number LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with db.closing_conn() as conn:
        rows = [_decorate(dict(r)) for r in conn.execute(sql, params)]
    if status:
        rows = [r for r in rows if r["status"] == status.upper()]
    # trim heavy fields for the table view
    for r in rows:
        r.pop("doc_text", None)
        r.pop("analysis", None)
    rows.sort(key=lambda r: (r["fit_score"] or 0), reverse=True)
    return {"count": len(rows), "rfps": rows}


@app.get("/api/rfps-facets")
def rfp_facets():
    """Distinct filter values (applicant types, states) for the dashboard."""
    with db.closing_conn() as conn:
        types = [r[0] for r in conn.execute(
            "SELECT DISTINCT applicant_type FROM rfps WHERE relevant=1 "
            "AND applicant_type IS NOT NULL AND applicant_type != '' "
            "ORDER BY applicant_type")]
        states = [r[0] for r in conn.execute(
            "SELECT DISTINCT state FROM rfps WHERE relevant=1 "
            "AND state IS NOT NULL AND state != '' ORDER BY state")]
    return {"applicant_types": types, "states": states}


@app.get("/api/rfps/{application_number}")
def get_rfp(application_number: str):
    with db.closing_conn() as conn:
        row = conn.execute("SELECT * FROM rfps WHERE application_number=?",
                           (application_number,)).fetchone()
        if row is None:
            raise HTTPException(404, "RFP not found")
        srs = [dict(r) for r in conn.execute(
            "SELECT * FROM service_requests WHERE application_number=?",
            (application_number,)).fetchall()]
        responses = [dict(r) for r in conn.execute(
            "SELECT id, created_at, docx_path, pdf_path, status "
            "FROM responses WHERE application_number=? ORDER BY id DESC",
            (application_number,)).fetchall()]
    out = _decorate(dict(row))
    out["doc_text_preview"] = (out.pop("doc_text", None) or "")[:5000]
    out["service_requests"] = srs
    out["responses"] = responses
    return out


@app.get("/api/rfps/{application_number}/documents/{name}")
def get_document(application_number: str, name: str):
    path = (config.DOCS_DIR / application_number / name).resolve()
    if not str(path).startswith(str(config.DOCS_DIR.resolve())) or \
            not path.exists():
        raise HTTPException(404, "document not found")
    return FileResponse(path)


@app.post("/api/rfps/{application_number}/analyze")
def analyze(application_number: str):
    result = ai.analyze_rfp(application_number, force=True)
    if result is None:
        raise HTTPException(
            503, "Analyst pass unavailable — is an AI provider key set "
                 "(NEMOTRON_API_KEY / ANTHROPIC_API_KEY)?")
    from . import scoring
    scoring.score_all(rescore=True)
    return {"analysis": result}


# ---------------------------------------------------------------------------
# Response generation
# ---------------------------------------------------------------------------

@app.post("/api/rfps/{application_number}/generate-response")
def generate_response(application_number: str):
    try:
        with keepawake.hold("response"):  # generation can take 1-2 min
            return respond.generate_response(application_number)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ---------------------------------------------------------------------------
# Keep-awake (prevent local machine sleep during long jobs; NOT an activity
# simulator — see README)
# ---------------------------------------------------------------------------

@app.get("/api/keepawake")
def keepawake_status():
    return keepawake.status()


@app.post("/api/keepawake")
def keepawake_set(payload: dict):
    return keepawake.set_manual(bool(payload.get("on")))


@app.get("/api/responses/{response_id}/download")
def download_response(response_id: int, fmt: str = "docx"):
    with db.closing_conn() as conn:
        row = conn.execute("SELECT * FROM responses WHERE id=?",
                           (response_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "response not found")
    path = Path(row["docx_path" if fmt == "docx" else "pdf_path"])
    if not path.exists():
        raise HTTPException(404, "file missing on disk")
    return FileResponse(path, filename=path.name)


# ---------------------------------------------------------------------------
# Price list
# ---------------------------------------------------------------------------

@app.post("/api/pricelist")
async def upload_pricelist(file: UploadFile = File(...),
                           mapping: str | None = Form(None)):
    content = await file.read()
    mapping_dict = json.loads(mapping) if mapping else None
    result = pricing_mod.import_price_list(file.filename or "pricelist.csv",
                                           content, mapping_dict)
    if result.get("ok"):
        from . import scoring
        scoring.score_all(rescore=True)  # catalog changed; rescore matches
    return result


@app.get("/api/pricelist")
def get_pricelist():
    with db.closing_conn() as conn:
        items = [dict(r) for r in conn.execute(
            "SELECT id, sku, description, category, unit, unit_price, "
            "term_months FROM price_items").fetchall()]
    return {"count": len(items), "items": items}


# ---------------------------------------------------------------------------
# Company profile
# ---------------------------------------------------------------------------

@app.get("/api/profile")
def get_profile():
    with db.closing_conn() as conn:
        profile = db.kv_get(conn, "company_profile", {})
    docs_dir = config.UPLOADS_DIR
    files = [f.name for f in docs_dir.iterdir() if f.is_file()]
    return {"profile": profile, "documents": files}


@app.put("/api/profile")
async def put_profile(profile: dict):
    with db.closing_conn() as conn:
        db.kv_set(conn, "company_profile", profile)
    return {"ok": True}


@app.post("/api/profile/documents")
async def upload_profile_document(file: UploadFile = File(...)):
    safe = Path(file.filename or "document").name
    dest = config.UPLOADS_DIR / safe
    dest.write_bytes(await file.read())
    return {"ok": True, "filename": safe}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.get("/api/settings")
def get_settings():
    return config.load_settings()


@app.put("/api/settings")
async def put_settings(new_settings: dict):
    saved = config.save_settings(new_settings)
    from . import scoring
    scoring.score_all(rescore=True)
    return saved


# ---------------------------------------------------------------------------
# Assistant chat
# ---------------------------------------------------------------------------

@app.post("/api/chat")
def chat_endpoint(payload: dict):
    from . import chat as chat_mod
    messages = payload.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise HTTPException(400, "messages list required")
    return chat_mod.run_chat(messages)


@app.post("/api/voice/converse")
async def voice_converse(audio: UploadFile = File(...),
                         messages: str = Form("[]"),
                         speak_reply: bool = Form(True)):
    """Speech-to-speech turn: transcribe -> assistant -> synthesize."""
    from . import chat as chat_mod, voice
    import base64
    if not voice.available():
        raise HTTPException(503, "voice requires NEMOTRON_API_KEY")
    wav = await audio.read()
    try:
        transcript = voice.transcribe(wav)
    except Exception as e:
        raise HTTPException(502, f"transcription failed: {e}")
    if not transcript:
        return {"transcript": "", "reply": "I didn't catch that — try again.",
                "navigate": None, "tool_log": [], "audio_b64": None}
    history = json.loads(messages or "[]")
    history.append({"role": "user", "content": transcript})
    result = chat_mod.run_chat(history, voice=True)
    audio_b64 = None
    if speak_reply and result.get("reply"):
        try:
            audio_b64 = base64.b64encode(
                voice.synthesize(result["reply"])).decode()
        except Exception as e:
            log.warning("TTS failed: %r", e)
    return {"transcript": transcript, **result, "audio_b64": audio_b64}


@app.post("/api/voice/speak")
async def voice_speak(payload: dict):
    """Text -> WAV (for speaking typed-chat replies aloud)."""
    from . import voice
    from fastapi.responses import Response
    if not voice.available():
        raise HTTPException(503, "voice requires NEMOTRON_API_KEY")
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text required")
    try:
        return Response(content=voice.synthesize(text[:4000]),
                        media_type="audio/wav")
    except Exception as e:
        raise HTTPException(502, f"synthesis failed: {e}")


@app.get("/api/health")
def health():
    from . import voice
    return {"ok": True, "ai_provider": config.llm_provider(),
            "voice_available": voice.available(),
            "ai_model": (config.NEMOTRON_MODEL
                         if config.llm_provider() == "nemotron"
                         else config.ANTHROPIC_MODEL),
            "usac_token_configured": bool(config.USAC_APP_TOKEN)}
