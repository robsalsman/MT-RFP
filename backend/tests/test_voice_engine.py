"""Matt's own voice (LuxTTS sidecar) with Magpie fallback."""
import httpx

from app import voice


class _Resp:
    def __init__(self, status=200, content=b"", payload=None):
        self.status_code = status
        self.content = content
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)


def _reset():
    voice._local_state.update(ok=False, checked=0.0)


def test_uses_local_voice_when_sidecar_healthy(monkeypatch):
    _reset()
    monkeypatch.setattr(httpx, "get",
                        lambda *a, **k: _Resp(200, payload={"ok": True}))
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: _Resp(200, content=b"RIFF....WAVE"))
    monkeypatch.setattr(voice, "_magpie",
                        lambda t: (_ for _ in ()).throw(AssertionError(
                            "Magpie must not be called")))
    assert voice.synthesize("Hello **Kim**").startswith(b"RIFF")
    assert voice.tts_engine() == "luxtts"


def test_falls_back_to_magpie_when_sidecar_down(monkeypatch):
    _reset()

    def down(*a, **k):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(httpx, "get", down)
    monkeypatch.setattr(voice, "_magpie", lambda t: b"MAGPIE:" + t.encode())
    assert voice.synthesize("Hello Kim") == b"MAGPIE:Hello Kim"
    assert voice.tts_engine() == "magpie"


def test_falls_back_to_magpie_when_sidecar_errors(monkeypatch):
    _reset()
    monkeypatch.setattr(httpx, "get",
                        lambda *a, **k: _Resp(200, payload={"ok": True}))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(500))
    monkeypatch.setattr(voice, "_magpie", lambda t: b"MAGPIE")
    assert voice.synthesize("Hello Kim") == b"MAGPIE"
    # the failure marks the sidecar unhealthy until the next health check
    assert voice._local_state["ok"] is False


def test_health_check_is_cached(monkeypatch):
    _reset()
    calls = []

    def get(*a, **k):
        calls.append(1)
        return _Resp(200, payload={"ok": True})
    monkeypatch.setattr(httpx, "get", get)
    assert voice.local_tts_ok() and voice.local_tts_ok()
    assert len(calls) == 1
