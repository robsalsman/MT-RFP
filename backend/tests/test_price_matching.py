"""Price-list import and requested-service matching."""
from pathlib import Path

from app import pricing

FIXTURE = Path(__file__).parent / "fixtures" / "sample_price_list.csv"


def _load_fixture(tmp_db):
    result = pricing.import_price_list("sample_price_list.csv",
                                       FIXTURE.read_bytes())
    assert result["ok"], result
    return result


def test_import_sample_price_list(tmp_db):
    result = _load_fixture(tmp_db)
    assert result["imported"] == 13
    assert result["row_errors"] == []


def test_header_sniffing_maps_aliases():
    mapping, missing = pricing.sniff_headers(
        ["SKU", "Description", "Service Category", "Unit", "Unit Price",
         "Term (months)"])
    assert missing == []
    assert mapping["unit_price"] == 4
    assert mapping["term_months"] == 5


def test_unknown_headers_request_mapping(tmp_db):
    csv = b"col_a,col_b\nwidget,10\n"
    result = pricing.import_price_list("x.csv", csv)
    assert result.get("needs_mapping")
    assert "description" in result["missing"]


def test_explicit_mapping_import(tmp_db):
    csv = b"col_a,col_b\n1G internet circuit,1250\n"
    result = pricing.import_price_list(
        "x.csv", csv, mapping={"description": 0, "unit_price": 1})
    assert result["ok"] and result["imported"] == 1


def test_bandwidth_aware_internet_match(tmp_db):
    _load_fixture(tmp_db)
    matches = pricing.match_services([{
        "service_type": "Data Transmission and/or Internet Access",
        "function": "Internet Access and Data Transmission Service",
        "quantity": "2", "max_capacity": "1024.00 Mbps",
        "min_capacity": "100.00 Mbps",
    }])
    m = matches[0]
    assert m["matched"] is True
    assert m["sku"] == "MT-IA-1G"  # 1024 Mbps ~ 1 Gbps tier
    assert m["unit_price"] == 1250.0
    assert m["quantity"] == 2
    assert m["extended_price"] == 2500.0


def test_wireless_ap_match(tmp_db):
    _load_fixture(tmp_db)
    matches = pricing.match_services([{
        "service_type": "Internal Connections",
        "function": "Wireless Access Points and Necessary Software and Licenses",
        "quantity": "40",
    }])
    m = matches[0]
    assert m["matched"] is True
    assert m["sku"] == "MT-WIFI-AP"
    assert m["extended_price"] == 40 * 685.0


def test_bad_prices_rejected():
    assert pricing._parse_price("$1,250.00") == 1250.0
    assert pricing._parse_price("-5") is None
    assert pricing._parse_price("call for quote") is None
    assert pricing._parse_price("") is None
