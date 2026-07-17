"""The no-fabrication guardrail: prices, identifiers, and company facts must
come from uploaded data or be [NEEDS INPUT] — never invented."""
from pathlib import Path

from app import pricing, respond
from app.respond import NEEDS_INPUT

FIXTURE = Path(__file__).parent / "fixtures" / "sample_price_list.csv"


def test_unmatched_request_gets_no_price(tmp_db):
    pricing.import_price_list("p.csv", FIXTURE.read_bytes())
    matches = pricing.match_services([{
        "service_type": "Internal Connections",
        "function": "Interactive Whiteboard Displays",  # not in catalog
        "quantity": "12",
    }])
    m = matches[0]
    assert m["matched"] is False
    assert m["unit_price"] is None
    assert m["extended_price"] is None


def test_maintenance_request_never_prices_hardware(tmp_db):
    pricing.import_price_list("p.csv", FIXTURE.read_bytes())
    matches = pricing.match_services([{
        "service_type": "Basic Maintenance of Internal Connections",
        "function": "Wireless Access Points",  # names hardware, but this is
        "quantity": "40",                      # a maintenance line item
    }])
    m = matches[0]
    # must either match a maintenance SKU or be flagged — never the AP SKU
    assert m["sku"] != "MT-WIFI-AP"


def test_empty_price_list_matches_nothing(tmp_db):
    matches = pricing.match_services([{
        "service_type": "Data Transmission and/or Internet Access",
        "function": "Internet Access", "quantity": "1",
    }])
    assert all(not m["matched"] for m in matches)


def test_scrub_strips_model_authored_dollar_amounts():
    narratives = {
        "cover_letter": "We can deliver this project for $49,999.99 total.",
        "compliance": [{"requirement": "E&O insurance",
                        "response": "We carry $2,000,000 in coverage.",
                        "compliance": "COMPLY"}],
    }
    respond._enforce_no_fabrication(narratives, profile={})
    assert "$49,999.99" not in narratives["cover_letter"]
    assert NEEDS_INPUT in narratives["cover_letter"]
    assert "$2,000,000" not in narratives["compliance"][0]["response"]


def test_scrub_strips_identifiers_missing_from_profile():
    narratives = {"cover_letter": "Our SPIN is 143001234.", "compliance": []}
    respond._enforce_no_fabrication(narratives, profile={"spin": "143099999"})
    assert "143001234" not in narratives["cover_letter"]
    assert NEEDS_INPUT in narratives["cover_letter"]


def test_scrub_keeps_identifiers_present_in_profile():
    narratives = {"cover_letter": "Our SPIN is 143099999.", "compliance": []}
    respond._enforce_no_fabrication(narratives, profile={"spin": "143099999"})
    assert "143099999" in narratives["cover_letter"]


def test_no_api_key_narratives_are_placeholders(monkeypatch):
    from app import ai, config
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "NEMOTRON_API_KEY", "")
    monkeypatch.setattr(config, "LLM_PROVIDER_OVERRIDE", "")
    out = ai.draft_narratives(
        row={"contact_name": "X"},
        analysis={"mandatory_requirements": ["Must hold a SPIN"]},
        profile={})
    assert NEEDS_INPUT in out["cover_letter"] or "NEEDS INPUT" in out["cover_letter"]
    assert out["compliance"][0]["response"] == NEEDS_INPUT
    assert out["compliance"][0]["compliance"] == "REVIEW"
