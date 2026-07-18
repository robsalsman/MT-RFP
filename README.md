# MT-RFP — Mission Telecom RFP Intelligence & Response Platform

Finds every currently-open E-Rate Form 470 / RFP in the K-12 & library
connectivity vertical across all 50 states, scores each for fit, and generates
draft RFP responses (DOCX + PDF) from Mission Telecom's uploaded price list.

**How it works:** ~95% of this market flows through the federal E-Rate
program. Every school/library seeking discounted connectivity files an FCC
Form 470 with USAC, opening a minimum 28-day competitive bidding window. USAC
publishes all of it as open data. MT-RFP pulls the Form 470 feed (dataset
`jt8s-3q52`), filters to relevant services, downloads attached RFP documents,
joins prior-year Form 471 spend (dataset `qdmp-ygft`) for deal sizing, and
computes open/closed status dynamically from today's date — no funding year is
ever hardcoded.

## Quick start

```bash
cp .env.example .env        # fill in NEMOTRON_API_KEY (and USAC_APP_TOKEN)
docker-compose up --build   # or: make run
```

- Dashboard: http://localhost:5173
- API: http://localhost:8000 (docs at /docs)

The backend runs a sync on startup and every 6 hours after; the first sync
pulls all Form 470s certified in the last 60 days across all states, scores
the open ones, and downloads attached RFP documents. Use **Refresh Now** in
the UI any time.

### Without Docker

```bash
make install                # backend pip install + frontend npm install
make dev-backend            # uvicorn on :8000
make dev-frontend           # vite on :5173 (separate terminal)
```

Windows without make: run the two commands from the Makefile directly.
If port 8000 is taken, start uvicorn on another port and set
`BACKEND_URL=http://127.0.0.1:<port>` when starting the frontend.

## USAC app token

Reads work anonymously but get throttled. Register a free app token at
https://opendata.usac.org (Sign up → Developer Settings → Create new app
token) and put it in `.env` as `USAC_APP_TOKEN`. The client already does
exponential backoff on 429s and caches responses (default 30 min TTL);
API use is strictly read-only.

## Using it

1. **Price List & Profile tab** — upload the price list (CSV/XLSX with SKU,
   description, service category, unit, unit price, term). Unrecognized
   headers open a column-mapping UI. Fill in the company profile (legal name,
   SPIN, FCC RN, contacts, references, capability statement) and upload
   supporting docs (insurance certs, W-9). A sample price list is at
   `backend/tests/fixtures/sample_price_list.csv`.
2. **Dashboard** — sortable/filterable table of open 470s: state, entity,
   type, services, fit score, est. prior spend (prior-FY Form 471 total for
   the same BEN), certified date, bid deadline (shown in Eastern time — always
   confirm against the RFP itself), status (OPEN / CLOSING SOON < 7 days /
   CLOSED), days left. Click a row for the full detail: score breakdown, AI
   analysis, original documents, extracted text.
3. **Assistant (💬, bottom-right)** — a natural-language helper that is an
   expert on the app, the E-Rate domain, AND Mission Telecom itself (plans,
   pricing, devices, programs, team — compiled from missiontelecom.org into
   `data/company_knowledge.md`, with source URLs so it can point people to
   the exact page). It answers from live data ("which deals close this
   week?", "why is Broome-Tioga scored 81?"), takes in-app actions (refresh
   data, run AI analysis, generate a draft, change scoring settings), and
   navigates the UI for you ("take me to the price list upload", "open the
   Shaker Heights RFP"). It is limited to read-only and draft-only actions —
   it cannot submit bids, upload files, or edit the price list/profile; for
   those it walks you to the right page.

   **Voice**: click 🎤 to speak to the assistant and hear it answer
   (speech-to-speech), or 🔊 to have typed replies read aloud. Speech runs
   on NVIDIA-hosted Riva services with the same NVIDIA API key — Parakeet
   ASR for speech-to-text, Magpie TTS for the voice — so there are no
   additional accounts. In voice mode the assistant answers in short spoken
   prose. Function IDs/voice are overridable in `.env` (see
   `.env.example`). The mic requires a secure context (localhost is fine).
4. **Generate Response** — one click on any OPEN RFP produces a DOCX + PDF
   named `{Entity}_{Form470No}_MissionTelecom_Response.docx` containing a
   cover letter, compliance matrix, pricing table, company info, and a
   required-forms checklist.

### Keep awake (☀ / ☕ in the top bar)

Long assistant-driven jobs — a full USAC sync, downloading and OCR-ing RFP
PDFs, generating a response — can run for minutes. The **Keep awake** toggle
tells the OS power manager to keep the machine and display on so those jobs
don't get interrupted by the computer sleeping. It engages automatically
while a sync or response generation is running (shows "auto") and can be
pinned on manually.

Implementation: Windows `SetThreadExecutionState` / macOS `caffeinate`
(`backend/app/keepawake.py`). It only requests "stay awake" from the OS — it
does **not** move the mouse, press keys, or simulate user activity, and it is
not an attendance/activity tool. (Only meaningful when the backend runs
directly on the user's machine; a container can't control host sleep.)

> Note: this replaced a request to bundle a random-mouse-mover to defeat
> employee idle/activity monitoring. That was intentionally **not** built —
> a tool whose purpose is to misrepresent whether someone is working
> deceives the employer, so only the honest keep-awake (which actually
> solves the sleep/timeout problem) is included.

### Guardrails (non-negotiable)

- Every response is stamped **DRAFT — NOT FOR SUBMISSION** with a mandatory
  human-review checklist. Nothing is ever auto-submitted anywhere.
- The pricing table is built deterministically from the uploaded price list.
  Requested items with no confident match are flagged **red / [NEEDS INPUT]**
  — prices are never invented.
- Company facts (SPIN, certifications, references, insurance) come only from
  the uploaded profile; anything missing renders as `[NEEDS INPUT]`. A
  post-generation scrubber additionally strips any model-authored dollar
  amounts and unrecognized identifiers.

## Fit scoring & Mission-Telecom biddability

Scoring is tuned to Mission Telecom's real business: a **nonprofit wireless
ISP on the T-Mobile 5G/4G network** that sells internet access / data
transmission (fixed wireless, cellular, hotspots) to schools and libraries.
It does **not** build fiber or sell/install LAN hardware. So the engine first
decides whether an RFP is even **biddable** (`app/mission_fit.py`, driven by
`config.MISSION_TELECOM`, derived from `data/company_knowledge.md`):

- **Biddable** — Category 1 "Internet Access and Data Transmission" (or
  standalone internet/data) that a wireless carrier can serve.
- **Not a fit** — requires leased fiber (lit/dark), or is Category 2
  internal-connections hardware only (switches, routers, firewalls, access
  points, cabling, UPS). These are flagged "not a fit" with the reason, and
  their rubric total is scaled down hard so they sink below every real
  opportunity. Biddability keys off the structured `function` field, not the
  noisy portal bandwidth values (a small school listing a 76 Gbps "minimum"
  is a data artifact, so bandwidth only flags a concern, never disqualifies).

The dashboard defaults to **Mission fit only** (a toggle turns it off to see
everything, with non-fits labelled). Then the 0–100 rubric ranks the biddable
ones, four buckets, weights configurable in Settings (`data/settings.json`):

| Bucket | Default | What it measures |
|---|---|---|
| Service match | 40 | How well the RFP matches Mission Telecom's wireless-connectivity catalog; bonus when it explicitly wants wireless/cellular/fixed-wireless, extra for modest bandwidth and library hotspot-lending. |
| Deal size | 20 | Log-scaled prior-FY Form 471 spend for the BEN; floor so small libraries still surface. |
| Winnability | 20 | Penalties for state/local restrictions, short remaining window, many mandatory requirements, disqualifiers; notes when the RFP confirms price as primary factor. |
| Strategic fit | 20 | Entity type (libraries and schools rank highest), explicit wireless demand, priority states, multi-year term. |

Every score carries a 2–3 sentence rationale (AI-written after the analyst
pass; deterministic fallback otherwise) plus a per-bucket breakdown and the
biddability verdict/blockers in the detail view. Tuning weights in Settings
rescores everything immediately.

**Filters:** the dashboard filters by Status, State, and entity Type, plus a
free-text search and the Mission-fit toggle — all also driveable from the
assistant ("show open libraries in Illinois", "which fiber RFPs did we skip?").

## Scheduler

`MTRFP_SYNC_INTERVAL_HOURS` (default 6) controls the background sync;
`MTRFP_LOOKBACK_DAYS` (default 60) the certified-date window. Each sync:
pull + paginate 470s → filter service types → upsert → join 471 prior spend →
download/extract RFP docs for open items (pdfplumber; optional OCR fallback —
see the commented lines in `backend/Dockerfile` / `requirements.txt`) →
score → AI analyst pass on new OPEN items.

## AI layer

Provider-pluggable. Default: **NVIDIA Nemotron** via the OpenAI-compatible
NVIDIA API (`NEMOTRON_API_KEY`, model `nvidia/nemotron-3-super-120b-a12b`,
configurable via `NEMOTRON_MODEL`/`NEMOTRON_BASE_URL`). Alternative:
Anthropic (`ANTHROPIC_API_KEY`, model via `ANTHROPIC_MODEL`). If both keys
are set, Nemotron wins; force a provider with
`MTRFP_LLM_PROVIDER=nemotron|anthropic`.

Two passes: an ingest-time **RFP Analyst** (structured extraction: services,
term, mandatory requirements, evaluation criteria, deadlines, disqualifiers)
and an on-demand **Response Generator** (cover letter + compliance matrix
narrative only — never pricing). Without an API key everything else still
works; AI fields show as unavailable.

## Tests

```bash
make test    # or: cd backend && python -m pytest tests -q
```

Covers the 28-day window math (incl. applicant-extended windows), SoQL
pagination, price-list import/mapping/matching, and the no-fabrication
guardrails.

## Phase 2 (stubbed)

State procurement portals (e.g. Texas ESBD, state DIR co-ops) for non-E-Rate
wireless solicitations: add a source module alongside `app/ingest.py` that
writes into the same `rfps` table with `application_number` prefixed by the
source (e.g. `ESBD-…`); status math and scoring are source-agnostic.

## Layout

```
backend/app/    config, db, soda (USAC client), status (window math),
                ingest (sync), spend (471 join), docs (PDF/DOCX text),
                scoring, ai, pricing, respond, main (FastAPI + scheduler)
backend/tests/  pytest suite + fixtures (sample price list)
frontend/src/   React dashboard (Dashboard, Detail, Uploads, Settings)
data/           SQLite DB, downloaded RFP docs, generated responses, settings
```
