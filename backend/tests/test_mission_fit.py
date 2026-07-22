"""Mission Telecom biddability: LTE is the product — the app must surface
RFPs carrying an explicit LTE/cellular signal (in the structured fields OR
the attached RFP document text), and exclude generic wired internet, fiber
builds, and Category 2 LAN hardware."""
import json

from app import mission_fit


def _row(service_types, functions, cat1=None, applicant_type="School",
         doc_text=None):
    return {"service_types": json.dumps(service_types),
            "functions": json.dumps(functions),
            "cat1_description": cat1, "cat2_description": None,
            "doc_text": doc_text, "applicant_type": applicant_type}


def test_plain_internet_access_without_lte_is_not_biddable():
    # generic internet access with no LTE/cellular signal anywhere — not
    # what Kim sells, must not surface as an opportunity
    fit = mission_fit.assess(
        _row(["Data Transmission and/or Internet Access"],
             ["Internet Access and Data Transmission Service"]),
        [{"min_capacity": "100.00 Mbps", "max_capacity": "500.00 Mbps"}])
    assert fit["biddable"] is False
    assert any("lte" in b.lower() for b in fit["blockers"])


def test_lte_in_rfp_document_makes_it_biddable():
    # applicants write generic "internet access" in the portal and only say
    # LTE inside the attached RFP document — the doc text must count
    fit = mission_fit.assess(
        _row(["Data Transmission and/or Internet Access"],
             ["Internet Access and Data Transmission Service"],
             doc_text="Vendor shall provide LTE wireless hotspot service "
                      "for student home connectivity."),
        [{"min_capacity": "100.00 Mbps", "max_capacity": "500.00 Mbps"}])
    assert fit["biddable"] is True
    assert fit["blockers"] == []
    assert fit["wireless_signal"] is True


def test_leased_fiber_is_not_biddable():
    fit = mission_fit.assess(
        _row(["Data Transmission and/or Internet Access"],
             ["Leased Lit Fiber", "Leased Dark Fiber",
              "Standalone Data Transmission Service"]),
        [{"min_capacity": "1000.00 Mbps", "max_capacity": "10000.00 Mbps"}])
    assert fit["biddable"] is False
    assert any("fiber" in b.lower() for b in fit["blockers"])


def test_category2_hardware_only_is_not_biddable():
    fit = mission_fit.assess(
        _row(["Internal Connections",
              "Basic Maintenance of Internal Connections"],
             ["Switches and Necessary Software and Licenses", "Cabling"]),
        [{"min_capacity": None, "max_capacity": None}])
    assert fit["biddable"] is False
    assert any("category 2" in b.lower() for b in fit["blockers"])


def test_inflated_bandwidth_does_not_disqualify():
    # a small school listing a 76.8 Gbps "minimum" is a portal artifact, not
    # a real fiber need — an LTE RFP must stay biddable, flagged as a concern.
    fit = mission_fit.assess(
        _row(["Data Transmission and/or Internet Access"],
             ["Internet Access and Data Transmission Service"],
             cat1="Cellular LTE data service for the district"),
        [{"min_capacity": "76800.00 Mbps", "max_capacity": "102400.00 Mbps"}])
    assert fit["biddable"] is True
    assert fit["concerns"]


def test_wireless_wan_signal_detected():
    fit = mission_fit.assess(
        _row(["Data Transmission and/or Internet Access"],
             ["Internet Access and Data Transmission Service"],
             cat1="School seeks fixed wireless / cellular LTE internet access"),
        [{"min_capacity": "50.00 Mbps", "max_capacity": "200.00 Mbps"}])
    assert fit["biddable"] is True
    assert fit["wireless_signal"] is True


def test_category2_wifi_hardware_is_not_a_wireless_wan_signal():
    fit = mission_fit.assess(
        _row(["Internal Connections"],
             ["Wireless Access Points and Necessary Software and Licenses",
              "Wireless Controllers"]),
        [{"min_capacity": None, "max_capacity": None}])
    assert fit["wireless_signal"] is False
    assert fit["biddable"] is False


def test_bandwidth_parser_ignores_year_and_junk():
    assert mission_fit._mbps("FY2027 Gateway to Learning") == 0.0
    assert mission_fit._mbps("1024.00 Mbps") == 1024.0
    assert mission_fit._mbps("1 Gbps") == 1000.0
    assert mission_fit._mbps("10G") == 10000.0
    assert mission_fit._mbps("500 Mbps") == 500.0
