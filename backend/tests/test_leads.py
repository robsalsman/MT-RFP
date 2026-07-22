"""Lead-gen classification: which Form 471 lines count as LTE/wireless.

The wireless flag drives who shows up as a lead — false positives waste
Kim's outreach, so the narrative matching is word-boundary strict."""
from app.leads import _LTE_NARRATIVE_RE, CELLULAR_CARRIERS, _consultant, \
    _norm_district


def _wireless_narrative(text: str) -> bool:
    return bool(_LTE_NARRATIVE_RE.search(text.lower()))


def test_lte_terms_match():
    assert _wireless_narrative("LTE hotspots for student home use")
    assert _wireless_narrative("cellular data service, 45 units")
    assert _wireless_narrative("Fixed Wireless internet for the annex")
    assert _wireless_narrative("4G failover via Cradlepoint routers")


def test_5gbps_fiber_is_not_5g():
    # the classic false positive: "5Gbps dedicated fiber" is NOT 5G cellular
    assert not _wireless_narrative("5Gbps dedicated fiber internet access")
    assert not _wireless_narrative("upgrade to 10Gbps WAN")
    assert _wireless_narrative("5G fixed wireless to the roof")


def test_lte_not_matched_inside_words():
    assert not _wireless_narrative("complete network refresh")
    assert not _wireless_narrative("alternate routing for the WAN")


def test_carrier_detection_list_has_the_k12_lte_players():
    joined = " ".join(CELLULAR_CARRIERS)
    for must in ("t-mobile", "verizon", "kajeet", "at&t mobility"):
        assert must in joined


def test_consultant_parse():
    assert _consultant("{Jane Doe|16062048|jane@erate.com|555-1234}") \
        == "Jane Doe <jane@erate.com>"
    assert _consultant(None) is None


def test_district_name_normalization():
    # USAC's "Dallas Indep School District" must match NCES's "DALLAS ISD"
    assert _norm_district("Dallas Indep School District") \
        == _norm_district("DALLAS ISD")
    assert _norm_district("Keller Independent School District") \
        == _norm_district("KELLER ISD")
