"""Matt's second brain: a native, Obsidian-compatible markdown vault.

Plain .md files under data/vault/ (openable in Obsidian if anyone ever
wants to — the app never needs it). Layout:

    kim.md            what Matt knows about Kim: preferences, rules, wins
    directives.md     how Kim has re-tuned Matt's hunting (append-only log)
    index.md          auto-generated map of the vault (regenerated nightly)
    accounts/*.md     one note per account Matt has worked
    playbook/*.md     tactics with a track record (lessons.md is the main one)
    journal/*.md      auto-written daily log of everything that happened
    inbox/*.md        raw intake: Kim's sticky notes, uploads, URL ingests
    library/*.md      full ingested source material (files, web pages)

Three write paths: deterministic event journaling (free, never forgets),
Kim feeding him directly (stickies / files / URLs), and a nightly LLM
consolidation pass that turns the journal + inbox into durable lessons.

Self-tuning: update_hunting() lets Matt change what the lead engines look
for — extra narrative terms, avoid terms, priority states — stored in kv
'hunt_prefs' and read live by leads.py and dailyrun.py, plus a free-text
directive log injected into his system prompt. Kim re-tunes him by talking
to him; nobody has to edit code.
"""
import datetime
import logging
import re
import threading
import time

import httpx

from . import ai, config, db, docs

log = logging.getLogger(__name__)

VAULT_DIR = config.DATA_DIR / "vault"
FILES_DIR = VAULT_DIR / "library" / "_files"   # raw uploaded files
SECTIONS = ("accounts", "playbook", "journal", "inbox", "library")
PREFS_KEY = "hunt_prefs"
CONSOLIDATED_KEY = "vault_consolidated"

_KIM_SEED = """# Kim

What Matt knows about Kim — preferences, standing rules, wins. Updated by
Matt when Kim tells him things, and by the nightly consolidation pass.

- Sells HOTSPOTS and CELL PHONES for Mission Telecom (nonprofit, T-Mobile).
- Works LIBRARIES only — schools have their own lead-gen people.
"""

_DIRECTIVES_SEED = """# Hunting directives

How Kim has re-tuned Matt's lead hunting, newest last. Matt appends here
via update_hunting when Kim tells him to look for things differently.
"""

_LESSONS_SEED = """# Playbook: lessons

Durable tactics with evidence. The nightly consolidation pass promotes
what works and retires what doesn't.
"""

_lock = threading.Lock()


def _ensure():
    for d in (VAULT_DIR, FILES_DIR, *(VAULT_DIR / s for s in SECTIONS)):
        d.mkdir(parents=True, exist_ok=True)
    for name, seed in (("kim.md", _KIM_SEED),
                       ("directives.md", _DIRECTIVES_SEED)):
        p = VAULT_DIR / name
        if not p.exists():
            p.write_text(seed, encoding="utf-8")
    lessons = VAULT_DIR / "playbook" / "lessons.md"
    if not lessons.exists():
        lessons.write_text(_LESSONS_SEED, encoding="utf-8")


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "note").lower()).strip("-")
    return s[:80] or "note"


def _resolve(rel_path: str):
    """Path inside the vault or ValueError — no escapes, .md only."""
    p = (VAULT_DIR / rel_path).resolve()
    if not str(p).startswith(str(VAULT_DIR.resolve())) or p.suffix != ".md":
        raise ValueError("bad vault path")
    return p


def _now() -> str:
    return datetime.datetime.now().strftime("%H:%M")


def _today() -> str:
    return datetime.date.today().isoformat()


# --- reading / browsing (powers the Brain tab) -----------------------------

def list_notes(section: str | None = None) -> list[dict]:
    _ensure()
    out = []
    roots = [VAULT_DIR / section] if section else \
        [VAULT_DIR, *(VAULT_DIR / s for s in SECTIONS)]
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.glob("*.md")):
            first = ""
            try:
                first = p.read_text(encoding="utf-8",
                                    errors="replace").lstrip()[:120]
            except OSError:
                pass
            title = first.splitlines()[0].lstrip("# ").strip() if first \
                else p.stem
            out.append({
                "path": str(p.relative_to(VAULT_DIR)).replace("\\", "/"),
                "section": p.parent.name if p.parent != VAULT_DIR else "root",
                "title": title, "size": p.stat().st_size,
                "updated": datetime.datetime.fromtimestamp(
                    p.stat().st_mtime).isoformat(timespec="minutes"),
            })
    out.sort(key=lambda n: n["updated"], reverse=True)
    return out


def read_note(rel_path: str) -> dict:
    p = _resolve(rel_path)
    if not p.exists():
        return {"error": "no such note"}
    return {"path": rel_path,
            "content": p.read_text(encoding="utf-8", errors="replace")}


def write_note(rel_path: str, content: str) -> dict:
    _ensure()
    p = _resolve(rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": rel_path}


def delete_note(rel_path: str) -> dict:
    p = _resolve(rel_path)
    if p.name in ("kim.md", "directives.md"):
        return {"error": "that note is core memory — edit it instead"}
    p.unlink(missing_ok=True)
    return {"ok": True}


def append_note(rel_path: str, text: str):
    _ensure()
    p = _resolve(rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(p, "a", encoding="utf-8") as f:
        f.write("\n" + text.rstrip() + "\n")


def search(q: str, limit: int = 12) -> list[dict]:
    """Case-insensitive substring search with a snippet per hit."""
    _ensure()
    ql = (q or "").lower().strip()
    if not ql:
        return []
    hits = []
    for n in list_notes():
        try:
            text = _resolve(n["path"]).read_text(encoding="utf-8",
                                                 errors="replace")
        except (OSError, ValueError):
            continue
        i = text.lower().find(ql)
        if i < 0:
            continue
        start = max(0, i - 80)
        hits.append({**n, "snippet":
                     text[start:i + len(ql) + 160].replace("\n", " ")})
        if len(hits) >= limit:
            break
    return hits


# --- write path 1: deterministic journaling --------------------------------

def journal(event: str):
    """Append one timestamped line to today's journal. Never raises."""
    try:
        append_note(f"journal/{_today()}.md",
                    f"- {_now()} {event.strip()}")
    except Exception as e:
        log.warning("vault journal failed: %s", e)


# --- write path 2: Kim feeds him directly ----------------------------------

def sticky(text: str, author: str = "Kim") -> dict:
    """A sticky note from the notepad — goes to his brain, not the chat."""
    _ensure()
    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    rel = f"inbox/sticky-{ts}.md"
    write_note(rel, f"# Sticky note from {author} ({_today()} {_now()})\n\n"
                    f"{text.strip()}\n")
    journal(f"sticky note from {author}: {text.strip()[:140]}")
    return {"ok": True, "path": rel}


def ingest_file(filename: str, data: bytes) -> dict:
    """Kim uploads a file to Matt's brain: keep the raw file, extract the
    text into library/, drop a pointer in the inbox for consolidation."""
    _ensure()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename or "file")[:120]
    raw = FILES_DIR / safe
    raw.write_bytes(data)
    text = docs.extract_text(raw)
    if not text:
        return {"error": f"couldn't extract text from {safe} — "
                         "PDF, DOCX, TXT and CSV work best"}
    summary = _summarize(text, f"file '{safe}' Kim uploaded")
    rel = f"library/{_slug(safe)}.md"
    write_note(rel, f"# {safe}\n\nUploaded by Kim {_today()}.\n\n"
                    f"## Summary\n{summary}\n\n## Extracted text\n"
                    f"{text[:20000]}\n")
    write_note(f"inbox/upload-{_slug(safe)}.md",
               f"# Upload: {safe} ({_today()})\n\nSee [[{_slug(safe)}]] in "
               f"library.\n\n{summary}\n")
    journal(f"Kim uploaded '{safe}' to my brain ({len(text):,} chars)")
    return {"ok": True, "path": rel, "summary": summary}


def ingest_url(url: str) -> dict:
    """Kim gives Matt a URL; he reads it into the vault — and files it
    smartly: a prospect's website or a person lands on that account's
    note, a story/article lands in the library. LinkedIn is login-walled
    (and scraping it violates their ToS), so those URLs are saved as a
    pointer on the account note instead of fetched."""
    _ensure()
    if not re.match(r"https?://", url or ""):
        url = "https://" + (url or "")
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
    if "linkedin.com" in host:
        return _ingest_linkedin(url)
    # honest bot UA first (Wikipedia et al. require it), then a browser
    # UA for sites that only whitelist browsers. Hard WAFs block both.
    ua_attempts = (
        "Mozilla/5.0 (compatible; MattRFP/1.0; +https://missiontelecom.org)",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    )
    resp, last_err = None, "unknown"
    for ua in ua_attempts:
        try:
            r = httpx.get(url, timeout=25, follow_redirects=True,
                          headers={"User-Agent": ua,
                                   "Accept-Language": "en-US,en;q=0.9"})
            r.raise_for_status()
            resp = r
            break
        except Exception as e:
            last_err = str(e)
    if resp is None:
        return {"error": f"couldn't fetch that page ({last_err[:120]}). "
                         "The site is blocking automated readers — copy "
                         "the text and stick it in my brain as a note "
                         "instead."}
    if "pdf" in (resp.headers.get("content-type") or ""):
        return ingest_file(url.rsplit("/", 1)[-1] or "download.pdf",
                           resp.content)
    from . import competitors   # late import — avoids a module cycle
    text = competitors._strip_html(resp.text)[:30000]
    if len(text) < 200:
        return {"error": "that page had no readable text"}
    kind, who, summary = _classify_page(text, url)
    name = _slug(re.sub(r"https?://", "", url))
    rel = f"library/url-{name}.md"
    write_note(rel, f"# {url}\n\nIngested {_today()} · looks like: {kind}"
                    f"{f' ({who})' if who else ''}.\n\n## Summary\n"
                    f"{summary}\n\n## Page text\n{text[:20000]}\n")
    write_note(f"inbox/url-{name}.md",
               f"# URL: {url} ({_today()})\n\n{summary}\n")
    filed_to = rel
    # a prospect org or a person gets the intel pinned to their account
    # note too, where drafts and recall will actually use it
    if kind in ("prospect", "person") and who:
        account_event(who, f"Kim fed me {url} — {summary[:400]}")
        filed_to = f"accounts/{_slug(who)}.md"
    journal(f"ingested URL {url} [{kind}{f': {who}' if who else ''}]")
    return {"ok": True, "path": rel, "summary": summary,
            "kind": kind, "name": who, "filed_to": filed_to}


def _classify_page(text: str, url: str):
    """(kind, name, summary): prospect | person | article, via the LLM."""
    raw = ai._chat(
        "You file web pages into a sales assistant's memory (client sells "
        "hotspots and cell phones to libraries/schools). Return STRICT "
        'JSON: {"kind": "prospect"|"person"|"article", "name": str|null, '
        '"summary": "4-6 tight bullet lines - facts, names, numbers, '
        'anything actionable"}. kind=prospect for an organization that '
        "could buy (a library, district, city, agency) - name it; "
        "kind=person for a page about one person - name them; "
        "kind=article for news/stories/reference. No other text.",
        f"URL: {url}\n\n{text[:12000]}", max_tokens=700)
    try:
        import json as _json
        m = re.search(r"\{.*\}", raw or "", re.DOTALL)
        d = _json.loads(m.group(0))
        kind = d.get("kind") if d.get("kind") in ("prospect", "person",
                                                  "article") else "article"
        return kind, (d.get("name") or "").strip() or None, \
            (d.get("summary") or "").strip() or "(no summary)"
    except Exception:
        return "article", None, (_summarize(text, f"web page {url}"))


def _ingest_linkedin(url: str) -> dict:
    """LinkedIn URLs: no fetch (login-walled + ToS). Save the pointer to
    the right account note so it's never lost, and ask Kim for the
    details worth keeping."""
    m = re.search(r"linkedin\.com/(in|company|school)/([^/?#]+)", url)
    slug = m.group(2) if m else ""
    pretty = slug.replace("-", " ").title().strip() or "Unknown"
    what = {"in": "person", "company": "company",
            "school": "school"}.get(m.group(1) if m else "", "profile")
    account_event(pretty, f"LinkedIn {what}: {url}")
    journal(f"saved LinkedIn {what} link for {pretty}")
    return {"ok": True, "kind": "linkedin", "name": pretty,
            "filed_to": f"accounts/{_slug(pretty)}.md",
            "summary": f"Saved {pretty}'s LinkedIn link to their account "
                       "note. I can't read LinkedIn itself (it's "
                       "login-walled and off-limits by their terms) — "
                       "paste me the highlights worth remembering and "
                       "I'll file them with it."}


def _summarize(text: str, what: str) -> str:
    out = ai._chat(
        "Summarize for a sales assistant's memory in 4-6 tight bullet "
        "lines: the facts, names, numbers, and anything actionable for "
        "selling hotspots/cell phones to schools and libraries. Plain "
        f"text bullets. This is {what}.",
        text[:12000], max_tokens=600)
    return (out or "").strip() or "(no summary — LLM offline)"


# --- write path 3: Matt remembers things from conversation -----------------

def remember(text: str, kind: str = "fact", org: str | None = None) -> dict:
    """Chat tool: save something durable. kind: kim|account|playbook|fact."""
    _ensure()
    stamp = f"({_today()})"
    text = text.strip()
    if kind == "kim":
        append_note("kim.md", f"- {text} {stamp}")
        target = "kim.md"
    elif kind == "account" and org:
        target = f"accounts/{_slug(org)}.md"
        p = _resolve(target)
        if not p.exists():
            write_note(target, f"# {org}\n")
        append_note(target, f"- {text} {stamp}")
    elif kind == "playbook":
        append_note("playbook/lessons.md", f"- {text} {stamp}")
        target = "playbook/lessons.md"
    else:
        target = f"inbox/note-{datetime.datetime.now():%Y-%m-%d-%H%M%S}.md"
        write_note(target, f"# Noted {stamp}\n\n{text}\n")
    journal(f"remembered [{kind}] {text[:140]}")
    return {"ok": True, "saved_to": target}


def account_event(org: str, event: str):
    """Deterministic account history — every touch lands in the note."""
    if not org:
        return
    try:
        target = f"accounts/{_slug(org)}.md"
        p = _resolve(target)
        if not p.exists():
            write_note(target, f"# {org}\n")
        append_note(target, f"- {_today()} {event.strip()}")
    except Exception as e:
        log.warning("vault account_event failed: %s", e)


# --- read paths ------------------------------------------------------------

def hot_context(max_chars: int = 3200) -> str:
    """Injected into every chat system prompt — his working memory."""
    _ensure()
    parts = ["\nMATT'S SECOND BRAIN (your vault — real persistent memory):"]
    try:
        kim = (VAULT_DIR / "kim.md").read_text(encoding="utf-8",
                                               errors="replace")
        parts.append("What you know about Kim:\n" + kim[-1400:])
        d = (VAULT_DIR / "directives.md").read_text(encoding="utf-8",
                                                    errors="replace")
        parts.append("Kim's hunting directives (you follow these):\n"
                     + d[-900:])
        lessons = (VAULT_DIR / "playbook" / "lessons.md").read_text(
            encoding="utf-8", errors="replace")
        parts.append("Playbook lessons:\n" + lessons[-700:])
        inbox = [n for n in list_notes("inbox")]
        if inbox:
            parts.append(f"Inbox: {len(inbox)} unprocessed note(s) from "
                         "Kim — recent titles: "
                         + "; ".join(n["title"][:60] for n in inbox[:4]))
    except Exception as e:
        log.warning("vault hot_context failed: %s", e)
    return "\n".join(parts)[:max_chars]


def lead_context(lead: dict, max_chars: int = 1200) -> str:
    """What Matt remembers about this account — for draft prompts."""
    try:
        p = _resolve(f"accounts/{_slug(lead.get('org') or '')}.md")
        if p.exists():
            return p.read_text(encoding="utf-8",
                               errors="replace")[-max_chars:]
    except (OSError, ValueError):
        pass
    return ""


# --- self-tuning hunting prefs ---------------------------------------------

def get_prefs() -> dict:
    with db.closing_conn() as conn:
        p = db.kv_get(conn, PREFS_KEY, {}) or {}
    return {"extra_terms": p.get("extra_terms", []),
            "avoid_terms": p.get("avoid_terms", []),
            "priority_states": p.get("priority_states", [])}


def update_hunting(directive: str, extra_terms=None, avoid_terms=None,
                   priority_states=None, clear: bool = False) -> dict:
    """Matt re-tunes his own hunting from conversation. The free-text
    directive is logged (and rides in his system prompt); the structured
    terms are applied live by the lead engines."""
    _ensure()
    p = {"extra_terms": [], "avoid_terms": [], "priority_states": []} \
        if clear else get_prefs()

    def _merge(key, vals, norm=lambda v: v.lower().strip()):
        for v in vals or []:
            v = norm(str(v))
            if v and v not in p[key] and len(p[key]) < 25:
                p[key].append(v)
    _merge("extra_terms", extra_terms)
    _merge("avoid_terms", avoid_terms)
    _merge("priority_states", priority_states,
           norm=lambda v: v.upper().strip()[:2])
    with db.closing_conn() as conn:
        db.kv_set(conn, PREFS_KEY, p)
        conn.commit()
    if directive:
        append_note("directives.md", f"- {_today()}: {directive.strip()}")
        journal(f"hunting re-tuned: {directive.strip()[:160]}")
    return {"ok": True, "prefs": p}


# --- write path 4: nightly consolidation (the sleep pass) ------------------

def consolidate(force: bool = False) -> dict:
    """Once a day: distill the recent journal + inbox into durable memory.
    Cheap when there's nothing new; safe to call opportunistically."""
    _ensure()
    today = _today()
    with db.closing_conn() as conn:
        done = db.kv_get(conn, CONSOLIDATED_KEY, "")
    if done == today and not force:
        return {"already_done": True}
    inbox = list_notes("inbox")
    recent_journal = []
    for delta in (1, 0):   # yesterday + today so far
        day = (datetime.date.today()
               - datetime.timedelta(days=delta)).isoformat()
        p = VAULT_DIR / "journal" / f"{day}.md"
        if p.exists():
            recent_journal.append(f"[{day}]\n" + p.read_text(
                encoding="utf-8", errors="replace")[-4000:])
    material = "\n\n".join(recent_journal)
    for n in inbox[:12]:
        try:
            material += "\n\nINBOX NOTE:\n" + _resolve(n["path"]).read_text(
                encoding="utf-8", errors="replace")[:2000]
        except (OSError, ValueError):
            continue
    applied = {"kim": 0, "playbook": 0}
    if material.strip():
        raw = ai._chat(
            "You are the memory-consolidation pass for Matt, a sales "
            "assistant working with Kim (sells hotspots and cell phones "
            "to libraries for Mission Telecom). From the journal lines "
            "and inbox notes, extract ONLY durable, reusable facts — "
            "skip one-off events. Return STRICT JSON: "
            '{"kim": ["fact about Kim/her preferences/rules", ...], '
            '"playbook": ["tactical lesson with evidence", ...]}. '
            "Empty arrays are fine. No other text.",
            material[:14000], max_tokens=1000)
        try:
            import json as _json
            m = re.search(r"\{.*\}", raw or "", re.DOTALL)
            data = _json.loads(m.group(0)) if m else {}
            for fact in (data.get("kim") or [])[:6]:
                append_note("kim.md", f"- {str(fact).strip()} ({today} auto)")
                applied["kim"] += 1
            for lesson in (data.get("playbook") or [])[:6]:
                append_note("playbook/lessons.md",
                            f"- {str(lesson).strip()} ({today} auto)")
                applied["playbook"] += 1
        except Exception as e:
            log.warning("consolidation parse failed: %s", e)
    # inbox notes are processed: fold them away (keep content in library/)
    done_dir = VAULT_DIR / "inbox" / "processed"
    done_dir.mkdir(exist_ok=True)
    for n in inbox:
        try:
            src = _resolve(n["path"])
            src.rename(done_dir / src.name)
        except (OSError, ValueError):
            pass
    _rebuild_index()
    with db.closing_conn() as conn:
        db.kv_set(conn, CONSOLIDATED_KEY, today)
        conn.commit()
    journal(f"consolidated memory: +{applied['kim']} Kim facts, "
            f"+{applied['playbook']} playbook lessons, "
            f"{len(inbox)} inbox notes processed")
    return {"ok": True, **applied, "inbox_processed": len(inbox)}


def maybe_consolidate_bg():
    """Fire-and-forget daily consolidation (called from busy endpoints)."""
    today = _today()
    with db.closing_conn() as conn:
        if db.kv_get(conn, CONSOLIDATED_KEY, "") == today:
            return
    threading.Thread(target=lambda: _safe_consolidate(), daemon=True).start()


def _safe_consolidate():
    try:
        consolidate()
    except Exception as e:
        log.warning("background consolidation failed: %s", e)


def _rebuild_index():
    lines = [f"# Vault index (rebuilt {_today()})", ""]
    for section in ("root", *SECTIONS):
        notes = [n for n in list_notes() if n["section"] == section]
        if not notes:
            continue
        lines.append(f"## {section} ({len(notes)})")
        lines += [f"- [[{n['path']}]] — {n['title'][:70]}"
                  for n in notes[:40]]
        lines.append("")
    (VAULT_DIR / "index.md").write_text("\n".join(lines), encoding="utf-8")
