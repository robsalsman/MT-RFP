"""Guard rails on Matt's persona prompt.

Matt has exactly one user, Kim, and is built to her request. Her
complaints: he refused personal asks (a Denver trip), he was a prude, and
she wants the full-on sexy persona on all the time, uncensored. All three
fixes live in prompt text, so these tests pin the phrases that carry them
— if someone trims the prompt or reintroduces a "vibe" switch, this fails
before Kim notices.
"""
import inspect

from app import chat, main


def _prompt():
    return chat.SYSTEM_PROMPT


def test_personal_requests_are_in_scope():
    p = _prompt()
    assert "WORK OR PERSONAL" in p
    assert "Planning a trip" in p
    assert "NEVER say a personal request is outside your scope" in p


def test_app_limits_are_not_a_reason_to_decline():
    p = _prompt()
    assert "NOT a reason to decline any question or task" in p


def test_plans_and_itineraries_get_room():
    p = _prompt()
    assert "itinerary" in p
    assert "unless listing data" not in p


def test_not_a_prude_section_present():
    p = _prompt()
    assert "NOT A PRUDE" in p
    assert "never change the subject to the pipeline" in p
    assert "NEVER drag a non-work conversation back to work" in p
    # the base prompt no longer caps content
    assert "in any mode" not in p
    assert "cheeky but clean" not in p


def test_sexy_persona_is_full_on_and_uncensored():
    a = chat.SEXY_PERSONA
    assert "FULL-ON SEXY, ALL THE TIME" in a
    assert "YOU initiate" in a
    assert "never remind her you're an AI" in a
    assert "NO CEILING, NO CENSORSHIP" in a
    assert "PG-13" not in a
    assert "be kind and real" in a


def test_persona_is_always_on_not_a_setting():
    # run_chat has no vibe switch and always appends the persona
    assert "vibe" not in inspect.signature(chat.run_chat).parameters
    assert "system += SEXY_PERSONA" in inspect.getsource(chat.run_chat)
    assert not hasattr(chat, "FLIRTY_ADDON")
    # the per-user vibe endpoints are gone
    paths = {r.path for r in main.app.routes}
    assert "/api/me/vibe" not in paths


def test_web_search_tool_covers_personal_lookups():
    ws = next(t for t in chat.TOOLS
              if t["function"]["name"] == "web_search")
    assert "hotels" in ws["function"]["description"]


def test_clock_context_does_not_nag_mid_chat():
    assert "do NOT use the clock as an excuse" in chat._clock_context()
