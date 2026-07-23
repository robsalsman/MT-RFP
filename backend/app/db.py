"""SQLite persistence layer. One connection per call; WAL mode for the
scheduler thread and request handlers to coexist."""
import json
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS rfps (
    application_number TEXT PRIMARY KEY,
    form_nickname TEXT,
    funding_year TEXT,
    billed_entity_number TEXT,
    billed_entity_name TEXT,
    applicant_type TEXT,
    state TEXT,
    city TEXT,
    zip TEXT,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    contact_address TEXT,
    website_url TEXT,
    certified_date TEXT,
    allowable_contract_date TEXT,
    form_pdf_url TEXT,
    rfp_doc_urls TEXT DEFAULT '[]',
    has_rfp_docs INTEGER DEFAULT 0,
    service_types TEXT DEFAULT '[]',
    functions TEXT DEFAULT '[]',
    cat1_description TEXT,
    cat2_description TEXT,
    state_or_local_restrictions INTEGER DEFAULT 0,
    relevant INTEGER DEFAULT 0,
    est_prior_spend REAL,
    fit_score REAL,
    score_breakdown TEXT,
    score_rationale TEXT,
    mission_biddable INTEGER,
    mission_blockers TEXT DEFAULT '[]',
    analysis TEXT,
    doc_text TEXT,
    doc_files TEXT DEFAULT '[]',
    last_synced TEXT
);
CREATE TABLE IF NOT EXISTS service_requests (
    application_number TEXT,
    service_request_id TEXT,
    service_category TEXT,
    service_type TEXT,
    function TEXT,
    quantity TEXT,
    unit TEXT,
    min_capacity TEXT,
    max_capacity TEXT,
    entities TEXT,
    manufacturer TEXT,
    PRIMARY KEY (application_number, service_request_id, service_type, function)
);
CREATE TABLE IF NOT EXISTS price_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT,
    description TEXT,
    category TEXT,
    unit TEXT,
    unit_price REAL,
    term_months INTEGER,
    raw TEXT
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_number TEXT,
    created_at TEXT,
    docx_path TEXT,
    pdf_path TEXT,
    checklist TEXT,
    unmatched_items TEXT,
    status TEXT DEFAULT 'DRAFT'
);
CREATE TABLE IF NOT EXISTS http_cache (
    url_hash TEXT PRIMARY KEY,
    url TEXT,
    fetched_at REAL,
    body BLOB
);
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS competitor_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ben TEXT NOT NULL,
    competitor TEXT NOT NULL,
    funding_year INTEGER,
    org TEXT,
    entity_type TEXT,
    state TEXT,
    spins TEXT DEFAULT '[]',
    spend REAL DEFAULT 0,
    next_expiration TEXT,
    contacts TEXT DEFAULT '[]',
    consultants TEXT DEFAULT '[]',
    narratives TEXT DEFAULT '[]',
    city TEXT,
    enrollment INTEGER,
    budget REAL,
    extra_contacts TEXT DEFAULT '[]',
    email_draft TEXT,
    status TEXT DEFAULT 'new',
    updated_at TEXT,
    UNIQUE(ben, competitor)
);
"""


def connect(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or config.DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path=None) -> None:
    with closing_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()


def _migrate(conn) -> None:
    """Add columns introduced after a DB was first created (CREATE TABLE
    IF NOT EXISTS won't alter an existing table)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(rfps)")}
    if "mission_biddable" not in cols:
        conn.execute("ALTER TABLE rfps ADD COLUMN mission_biddable INTEGER")
    if "mission_blockers" not in cols:
        conn.execute(
            "ALTER TABLE rfps ADD COLUMN mission_blockers TEXT DEFAULT '[]'")
    ccols = {r[1] for r in conn.execute(
        "PRAGMA table_info(competitor_leads)")}
    if ccols:
        # funding program the lead was found in: 'erate' (recurring annual
        # spend) or 'ecf' (one-time hotspot program -> win-back targets)
        if "source" not in ccols:
            conn.execute("ALTER TABLE competitor_leads ADD COLUMN "
                         "source TEXT DEFAULT 'erate'")
        if "devices" not in ccols:
            conn.execute(
                "ALTER TABLE competitor_leads ADD COLUMN devices INTEGER")


@contextmanager
def closing_conn(db_path=None):
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def kv_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def kv_set(conn, key, value):
    conn.execute(
        "INSERT INTO kv (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )
    conn.commit()
