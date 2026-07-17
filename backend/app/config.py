"""Central configuration for MT-RFP.

Environment (.env) holds secrets; data/settings.json holds tunable scoring
weights and strategic-fit preferences (editable via the Settings UI).
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.environ.get("MTRFP_DATA_DIR", BASE_DIR / "data"))
DOCS_DIR = DATA_DIR / "rfp_docs"
RESPONSES_DIR = DATA_DIR / "responses"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = Path(os.environ.get("MTRFP_DB_PATH", DATA_DIR / "mtrfp.db"))
SETTINGS_PATH = DATA_DIR / "settings.json"

for d in (DATA_DIR, DOCS_DIR, RESPONSES_DIR, UPLOADS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- External services ---------------------------------------------------
USAC_BASE = "https://opendata.usac.org/resource"
DATASET_FORM470 = "jt8s-3q52"       # Form 470 Tool Data (primary feed)
DATASET_FORM470_BASIC = "jp7a-89nd"
DATASET_FORM470_SERVICES = "39tn-hjzv"
DATASET_FRN_STATUS = "qdmp-ygft"    # Form 471 FRN Status (prior-spend join)

USAC_APP_TOKEN = os.environ.get("USAC_APP_TOKEN", "")

# --- AI provider ----------------------------------------------------------
# Nemotron (NVIDIA API, OpenAI-compatible) is the default provider when its
# key is set; Anthropic is supported as an alternative. MTRFP_LLM_PROVIDER
# can force one explicitly ("nemotron" | "anthropic").
NEMOTRON_API_KEY = os.environ.get("NEMOTRON_API_KEY", "")
NEMOTRON_BASE_URL = os.environ.get(
    "NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1")
NEMOTRON_MODEL = os.environ.get(
    "NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
LLM_PROVIDER_OVERRIDE = os.environ.get("MTRFP_LLM_PROVIDER", "")


def llm_provider() -> str | None:
    """Active AI provider name, or None when no key is configured."""
    if LLM_PROVIDER_OVERRIDE:
        return LLM_PROVIDER_OVERRIDE
    if NEMOTRON_API_KEY:
        return "nemotron"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return None

# --- Sync behaviour -------------------------------------------------------
SYNC_LOOKBACK_DAYS = int(os.environ.get("MTRFP_LOOKBACK_DAYS", "60"))
SYNC_INTERVAL_HOURS = float(os.environ.get("MTRFP_SYNC_INTERVAL_HOURS", "6"))
SODA_PAGE_SIZE = int(os.environ.get("MTRFP_SODA_PAGE_SIZE", "1000"))
HTTP_CACHE_TTL_SECONDS = int(os.environ.get("MTRFP_HTTP_CACHE_TTL", "1800"))
CLOSING_SOON_DAYS = 7
BID_WINDOW_DAYS = 28  # E-Rate minimum competitive bidding window

# Deadlines display timezone: applicants are local but E-Rate deadlines are
# commonly stated Eastern.
EASTERN_TZ = "America/New_York"

# --- Default tunable settings (data/settings.json overrides) --------------
DEFAULT_SETTINGS = {
    "scoring_weights": {
        "service_match": 40,
        "deal_size": 20,
        "winnability": 20,
        "strategic_fit": 20,
    },
    "deal_size": {
        # log-scaled between floor and ceiling; small libraries still surface
        "floor_points": 5,
        "full_points_at_annual_spend": 250000,
    },
    "strategic_fit": {
        "priority_states": ["TX", "CA", "FL", "NY"],
        "priority_state_points": 8,
        "entity_type_points": {"School District": 6, "School": 5, "Library": 4,
                               "Library System": 4, "Consortium": 6},
        "preferred_contract_years_min": 3,
        "multi_year_points": 6,
    },
    # Mission Telecom's core catalog categories. Used for service-match until a
    # price list is uploaded, then augmented by the price list's categories.
    "core_services": [
        "internet access", "data transmission", "wireless", "cellular",
        "wi-fi", "wifi", "leased lit fiber", "broadband",
    ],
    "secondary_services": [
        "internal connections", "wireless access points", "access points",
        "wireless controllers", "switches", "routers", "firewall",
        "managed internal broadband", "basic maintenance", "cabling",
        "leased dark fiber", "antennas",
    ],
}


def load_settings() -> dict:
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy
    if SETTINGS_PATH.exists():
        try:
            user = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            _deep_merge(settings, user)
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save_settings(new_settings: dict) -> dict:
    settings = load_settings()
    _deep_merge(settings, new_settings)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return settings


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
