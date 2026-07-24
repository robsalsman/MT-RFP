"""New lead sources: consultant dedup, DDG URL decoding, contact parsing."""
from app.consultants import _norm
from app.mentions import _real_url, _clean
from app.competitors import _parse_contact


def test_consultant_name_dedup():
    # the same firm files under many spellings
    assert _norm("E-RATE CENTRAL") == _norm("E-Rate Central")
    assert _norm("CSM CONSULTING INC.") == _norm("CSM Consulting, Inc")
    assert _norm("Kellogg & Sovereign Consulting, LLC") \
        == _norm("KELLOGG & SOVEREIGN CONSULTING")


def test_consultant_norm_distinguishes_firms():
    assert _norm("E-Rate Central") != _norm("E-Rate Online")


def test_ddg_redirect_decode():
    u = ("//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.example.org%2Fboard"
         "%2Fminutes.pdf&rut=abc")
    assert _real_url(u) == "https://www.example.org/board/minutes.pdf"
    assert _real_url("https://plain.example.com/x") \
        == "https://plain.example.com/x"


def test_html_clean():
    assert _clean("<b>Mobile&nbsp;Beacon</b> <i>rocks</i>") \
        == "Mobile\xa0Beacon rocks"


def test_parse_contact_formats():
    assert _parse_contact("Jane Doe <jane@dallasisd.org>") \
        == ("Jane Doe", "jane@dallasisd.org")
    assert _parse_contact("it@nps.k12.nj.us") == (None, "it@nps.k12.nj.us")
    assert _parse_contact("Just A Name") == ("Just A Name", None)
