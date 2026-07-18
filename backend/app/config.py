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
        # Mission Telecom's field is under-resourced K-12 & libraries; its
        # library hotspot-lending program (Project: Volume Up) makes libraries
        # an especially strong fit.
        "priority_states": [],
        "priority_state_points": 6,
        "entity_type_points": {"Library": 10, "Library System": 10,
                               "School": 8, "Consortium": 6,
                               "School District": 7},
        "preferred_contract_years_min": 1,
        "multi_year_points": 4,
    },
}

# --- Mission Telecom capability profile -----------------------------------
# Derived from missiontelecom.org (see data/company_knowledge.md). Mission
# Telecom is a NONPROFIT WIRELESS ISP running on the T-Mobile 5G/4G network.
# It sells internet access / data transmission delivered over fixed wireless
# and cellular (mobile hotspots, connected tablets, BYOD) to schools and
# libraries. It does NOT build fiber and does NOT sell/install LAN hardware
# (switches, routers, firewalls, wireless access points, cabling, UPS).
#
# Scoring uses this to find the RFPs Mission Telecom can actually bid on and
# win: E-Rate Category 1 internet access / data transmission at bandwidths
# deliverable over wireless — not fiber builds, multi-gig circuits, or
# Category 2 internal-connections hardware.
MISSION_TELECOM = {
    # E-Rate service the company bids on (Category 1 connectivity)
    "core_service_types": [
        "data transmission and/or internet access",
    ],
    # what Mission Telecom actually delivers (wireless connectivity)
    "core_terms": [
        "internet access", "data transmission", "broadband", "wan",
        "wireless", "cellular", "lte", "5g", "4g", "fixed wireless",
        "hotspot", "mobile data", "mobile hotspot",
    ],
    # exact-niche signals that make an RFP an especially strong fit
    "sweet_spot_terms": [
        "fixed wireless", "wireless", "cellular", "lte", "5g", "hotspot",
        "mobile", "wi-fi hotspot", "lending",
    ],
    # requested services/functions Mission Telecom CANNOT deliver:
    # dedicated fiber builds, and Category 2 internal-connections hardware.
    "cannot_deliver_terms": [
        "leased dark fiber", "leased lit fiber", "dark fiber", "lit fiber",
        "switch", "router", "firewall", "cabling", "access point",
        "wireless controller", "antenna", "uninterruptable", "ups",
        "battery backup", "rack", "structured cabling", "caching",
    ],
    # E-Rate service categories that are LAN hardware, not Mission's business
    "excluded_service_types": [
        "internal connections",
        "basic maintenance of internal connections",
        "managed internal broadband services",
    ],
    # realistic delivery ceiling for fixed wireless / cellular, in Mbps.
    # Above this a wireless carrier can't serve the circuit.
    "max_deliverable_mbps": 1000,
    "sweet_spot_mbps": 500,
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
