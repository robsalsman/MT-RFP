"""Reading library websites for a word, and failing loudly enough to fix."""
import httpx
import pytest

from app import chat, libraries


class _Resp:
    def __init__(self, text="", status=200):
        self.text = text
        self.status_code = status
        self.url = "https://www.example.org"


def _serve(monkeypatch, pages: dict, search=None):
    """Fake the web: {url_substring: html} plus optional search results."""
    def get(url, **kw):
        for frag, html in pages.items():
            if frag in url:
                r = _Resp(html)
                r.url = url
                return r
        return _Resp("", 404)
    monkeypatch.setattr(libraries.httpx, "get", get)
    from app import mentions
    monkeypatch.setattr(mentions, "web_search",
                        lambda q, limit=8: list(search or []))


def test_reads_the_page_and_quotes_it(monkeypatch):
    _serve(monkeypatch, {
        "lib.org": "<html><body>The library lends a mobile HOTSPOT to any "
                   "cardholder for three weeks.</body></html>"})
    r = libraries._pages_mentioning("lib.org", "hotspot")
    assert r["status"] == "found"
    assert "HOTSPOT" in r["hits"][0]["snippet"]
    assert r["hits"][0]["from"] == "page"


def test_a_search_hit_is_confirmed_on_the_real_page(monkeypatch):
    _serve(monkeypatch,
           {"/wifi": "<html>Borrow a hotspot from the front desk</html>",
            "lib.org": "<html><body>welcome</body></html>"},
           search=[{"url": "https://www.lib.org/wifi", "title": "WiFi",
                    "snippet": "hotspots to borrow"}])
    r = libraries._pages_mentioning("lib.org", "hotspot")
    assert r["hits"][0]["from"] == "page"       # not taken on trust
    assert "front desk" in r["hits"][0]["snippet"]


def test_a_script_rendered_page_is_read_from_its_payload(monkeypatch):
    """A JS shell renders no text, but ships the words in the payload —
    quote them, and say that's where they came from."""
    _serve(monkeypatch, {
        "/news/wifi": '<html><body><div id="app"></div><script>'
                      'window.__DATA={"title":"Borrow a hotspot free for '
                      'three weeks from any branch"}</script></body></html>',
        "lib.org": "<html><body><a href='/news/wifi'>News</a></body></html>"})
    r = libraries._pages_mentioning("lib.org", "hotspot")
    assert r["hits"][0]["from"] == "page source"
    assert "three weeks" in r["hits"][0]["snippet"]


def test_a_search_results_page_cannot_match_itself(monkeypatch):
    """?s=hotspot echoes the query back — if that counted, every library
    on earth would look like a match."""
    _serve(monkeypatch, {
        "?s=": "<html><body>Search results for: hotspot — nothing found."
               "</body></html>",
        "lib.org": "<html><body>" + ("Story time. " * 200) + "</body></html>"})
    assert libraries._pages_mentioning("lib.org", "hotspot")["status"] \
        == "no mention"


def test_an_unreadable_site_is_never_reported_as_a_no(monkeypatch):
    """The whole point: 'we couldn't read it' must not become 'they don't
    mention it' — that would send Kim past a warm lead."""
    _serve(monkeypatch, {"lib.org": "<html><body><div id=app></div></body>"
                                    "</html>"})
    assert libraries._pages_mentioning("lib.org", "hotspot")["status"] \
        == "unreadable"


def test_a_readable_site_without_the_word_is_a_real_no(monkeypatch):
    body = "Story time at the branch. " * 60
    _serve(monkeypatch, {"lib.org": f"<html><body>{body}</body></html>"})
    assert libraries._pages_mentioning("lib.org", "hotspot")["status"] \
        == "no mention"


def test_scan_separates_matches_from_unknowns(tmp_db, monkeypatch):
    from app import db
    with db.closing_conn() as conn:
        for i, (org, site) in enumerate([("A Public Library", "a.org"),
                                         ("B Public Library", "b.org"),
                                         ("C Public Library", None)]):
            conn.execute(
                "INSERT INTO competitor_leads (ben, competitor, org, "
                "entity_type, state, spend, status, website, source) VALUES "
                "(?,'greenfield',?,'Library System','OH',0,'new',?,'imls')",
                (f"L{i}", org, site))
        conn.commit()
    _serve(monkeypatch, {
        "a.org": "<html>We lend a hotspot, free.</html>",
        "b.org": "<html><body><div id=app></div></body></html>"})
    monkeypatch.setattr(libraries, "_find_domain", lambda lead: None)
    r = libraries.scan_sites("hotspot", limit=10)
    assert [m["org"] for m in r["matches"]] == ["A Public Library"]
    assert r["could_not_read"] == ["B Public Library"]
    assert r["no_website_on_file"] == ["C Public Library"]
    assert "not a no" in r["note"].lower()


def test_running_out_of_time_is_not_reported_as_a_no(tmp_db, monkeypatch):
    """A scan is wall-clocked so Kim isn't left waiting. The libraries it
    didn't reach are unknown — the one thing they must never look like is
    'checked, doesn't mention it'."""
    from app import db
    with db.closing_conn() as conn:
        conn.execute(
            "INSERT INTO competitor_leads (ben, competitor, org, "
            "entity_type, state, spend, status, website, source) VALUES "
            "('L9','greenfield','Slow Public Library','Library System',"
            "'OH',0,'new','slow.org','imls')")
        conn.commit()
    _serve(monkeypatch, {"slow.org": "<html>plenty of words here</html>"})
    monkeypatch.setattr(libraries, "SCAN_SECONDS", -1)     # already expired
    r = libraries.scan_sites("hotspot", limit=5)
    assert r["not_reached_in_time"] == ["Slow Public Library"]
    assert r["matches"] == [] and r["libraries_read"] == 0
    assert "time limit" in r["note"]


def test_matt_has_a_tool_for_it(tmp_db, monkeypatch):
    """Kim's actual ask — 'libraries with hotspot on their website' — has
    to be one tool call, not something Matt says he can't do."""
    names = [t["function"]["name"] for t in chat.TOOLS]
    assert "find_libraries_saying" in names
    called = {}

    def fake(*a, **k):
        called["args"] = a
        return {"matches": []}
    monkeypatch.setattr(libraries, "scan_sites", fake)
    chat._exec_tool("find_libraries_saying", {"term": "hotspot",
                                              "state": "ohio", "limit": 5})
    assert called["args"] == ("hotspot", "OH", 5)


# --- when the model call fails, say what actually broke -------------------

def _http_error(code, body=""):
    req = httpx.Request("POST", "https://api.example/v1/chat/completions")
    return httpx.HTTPStatusError("boom", request=req,
                                 response=httpx.Response(code, text=body,
                                                         request=req))


@pytest.mark.parametrize("err, expect", [
    (_http_error(401), "key"),
    (_http_error(429), "rate-limited"),
    (_http_error(400, "maximum context length exceeded"), "two parts"),
    (_http_error(503), "wobble"),
    (httpx.ReadTimeout("slow"), "smaller ask"),
])
def test_the_error_tells_kim_what_happened(err, expect):
    detail, friendly = chat._describe_llm_error(err)
    assert expect in friendly
    assert detail            # and the log gets the provider's own words


def test_the_provider_response_body_reaches_the_log():
    detail, _ = chat._describe_llm_error(
        _http_error(400, "context length exceeded: 200000 tokens"))
    assert "200000 tokens" in detail


def test_too_much_tool_output_is_trimmed_instead_of_giving_up():
    assert chat._is_context_error(
        _http_error(400, "This model's maximum context length is 131072"))
    assert not chat._is_context_error(_http_error(400, "bad request"))
    convo = [{"role": "system", "content": "x" * 5000},
             {"role": "tool", "content": "y" * 20000},
             {"role": "tool", "content": "short"}]
    assert chat._shrink_tool_payloads(convo) is True
    assert len(convo[1]["content"]) < 1000
    assert convo[0]["content"] == "x" * 5000     # system prompt untouched
    assert convo[2]["content"] == "short"
    assert chat._shrink_tool_payloads(convo) is False   # nothing left


# --- the persona Kim actually gets ---------------------------------------

def test_flirty_mode_woos_her_and_keeps_its_guardrails():
    a = chat.FLIRTY_ADDON.lower()
    assert "woo her" in a and "rock star" in a
    for rule in ("pg-13", "never explicit", "never possessive",
                 "never negging", "real data still come first"):
        assert rule in a, rule


def test_he_is_told_to_love_being_dressed():
    p = chat.SYSTEM_PROMPT
    assert "WHEN SHE DRESSES YOU" in p
    assert "don't get used to it" in p     # the exact line she got, banned
