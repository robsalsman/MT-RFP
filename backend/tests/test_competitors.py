"""Competitor displacement: spin classification, contact filtering, and the
best-contact pick that decides who Kim's email goes to."""
from app import competitors


def test_spin_classification():
    assert competitors.competitor_for_spin("Kajeet, Inc.") == "kajeet"
    assert competitors.competitor_for_spin(
        "Verizon Wireless (Cellco Partnership)") == "verizon"
    assert competitors.competitor_for_spin("AT&T Mobility") == "att"
    assert competitors.competitor_for_spin("Mobile Beacon") == "mobile_beacon"


def test_tmobile_is_not_a_competitor():
    # Mission Telecom delivers ON T-Mobile — never target them
    assert competitors.competitor_for_spin("T-Mobile USA, Inc.") is None
    assert competitors.competitor_for_spin(
        "Guadalupe Valley Telephone Cooperative") is None


def test_district_domain_skips_consultants():
    lead = {"contacts": ["jane@e-ratecentral.com", "it@dallasisd.org"]}
    assert competitors.district_domain(lead) == "dallasisd.org"
    assert competitors.district_domain(
        {"contacts": ["x@edtechnologyfunds.com"]}) is None
    assert competitors.district_domain({"contacts": []}) is None


def test_best_contact_prefers_tech_leadership():
    lead = {"extra_contacts": [
        {"name": "Pat Smith", "title": "Athletics", "email": "p@x.org"},
        {"name": "Lee Chan", "title": "Director of Technology",
         "email": "l@x.org"}],
        "contacts": ["filing@x.org"]}
    assert competitors._best_contact(lead)["email"] == "l@x.org"


def test_best_contact_falls_back_to_filing_email():
    assert competitors._best_contact(
        {"extra_contacts": [], "contacts": ["filing@x.org"]}
    )["email"] == "filing@x.org"
