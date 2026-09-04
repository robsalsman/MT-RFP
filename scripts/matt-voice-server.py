"""Matt's voice: a warm LuxTTS sidecar that speaks in Rob's cloned voice.

Runs under the LuxTTS virtualenv (NOT the app's Python) because LuxTTS
brings its own torch/onnx stack:

    C:\\Users\\robsa\\Apps\\LuxTTS\\.venv\\Scripts\\python scripts\\matt-voice-server.py

The model takes ~40 s to load and ~1 s of GPU time per sentence, so it
stays resident and the app calls it over HTTP:

    GET  /health                -> {"ok": true, "reference": "...", ...}
    POST /synthesize {"text": "...", "speed": 1.0}  -> audio/wav (48 kHz mono)

The reference clip is data/voice/matt-reference.wav (a copy of the "Rob"
voice from the Fraud Signal studio). Override with MATT_VOICE_REFERENCE.
Rendering parameters match the studio's render_studio_voice.py so Matt
sounds the same as the channel narration.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LUX_ROOT = Path(os.environ.get("LUXTTS_ROOT", r"C:\Users\robsa\Apps\LuxTTS"))
MODEL_PATH = LUX_ROOT / "models" / "YatharthS-LuxTTS"
REFERENCE = Path(os.environ.get("MATT_VOICE_REFERENCE",
                                ROOT / "data" / "voice" / "matt-reference.wav"))
PORT = int(os.environ.get("MATT_VOICE_PORT", "8030"))
SAMPLE_RATE = 48000
CHUNK_CHARS = 260
GAP_SECONDS = 0.28
MAX_TEXT = 4000

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("matt-voice")

sys.path.insert(0, str(LUX_ROOT))


def chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
    result, cur = [], ""
    for s in sentences:
        while len(s) > limit:  # pathological run-on
            result.append(s[:limit])
            s = s[limit:]
        cand = f"{cur} {s}".strip()
        if cur and len(cand) > limit:
            result.append(cur)
            cur = s
        else:
            cur = cand
    if cur:
        result.append(cur)
    return result or ([text] if text else [])


class Voice:
    def __init__(self):
        import numpy as np
        import torch
        import soundfile as sf
        from zipvoice.luxvoice import LuxTTS
        self.np, self.torch, self.sf = np, torch, sf
        t0 = time.time()
        self.model = LuxTTS(str(MODEL_PATH), device="cuda")
        self.loaded_in = round(time.time() - t0, 1)
        self.lock = threading.Lock()
        self.reference_mtime = 0.0
        self.encoded = None
        self._encode()
        log.info("model loaded in %ss, reference %s", self.loaded_in, REFERENCE)

    def _encode(self):
        # Re-encode when the reference file changes (drop a new clip in, no restart).
        mtime = REFERENCE.stat().st_mtime
        if self.encoded is None or mtime != self.reference_mtime:
            self.encoded = self.model.encode_prompt(str(REFERENCE), duration=8,
                                                    rms=0.012)
            self.reference_mtime = mtime

    def speak(self, text: str, speed: float = 1.0) -> bytes:
        np, torch = self.np, self.torch
        speed = max(0.75, min(1.25, float(speed or 1.0)))
        parts = []
        with self.lock:
            self._encode()
            for seg in chunks(text):
                with torch.inference_mode():
                    wav = self.model.generate_speech(
                        seg, self.encoded, num_steps=4, guidance_scale=3.0,
                        t_shift=0.82, speed=speed, return_smooth=False)
                parts.append(wav.detach().cpu().numpy().squeeze()
                             .astype(np.float32))
                parts.append(np.zeros(round(GAP_SECONDS * SAMPLE_RATE),
                                      dtype=np.float32))
        if not parts:
            return b""
        combined = np.concatenate(parts)
        peak = float(np.max(np.abs(combined))) or 1.0
        if peak > 0.96:
            combined *= 0.96 / peak
        buf = io.BytesIO()
        self.sf.write(buf, combined, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return buf.getvalue()


VOICE: Voice | None = None
LOAD_ERROR: str | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter than the default
        log.debug(fmt, *args)

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._json(200 if VOICE else 503, {
                "ok": VOICE is not None, "engine": "luxtts",
                "reference": str(REFERENCE), "load_error": LOAD_ERROR,
                "loaded_in_s": VOICE.loaded_in if VOICE else None})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/synthesize":
            return self._json(404, {"error": "not found"})
        if VOICE is None:
            return self._json(503, {"error": LOAD_ERROR or "model loading"})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})
        text = str(payload.get("text") or "").strip()[:MAX_TEXT]
        if not text:
            return self._json(400, {"error": "text required"})
        t0 = time.time()
        try:
            wav = VOICE.speak(text, payload.get("speed", 1.0))
        except Exception as e:
            log.exception("synthesis failed")
            return self._json(500, {"error": repr(e)})
        log.info("spoke %d chars in %.2fs", len(text), time.time() - t0)
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav)))
        self.end_headers()
        self.wfile.write(wav)


def _load():
    global VOICE, LOAD_ERROR
    try:
        if not REFERENCE.exists():
            raise FileNotFoundError(f"reference clip missing: {REFERENCE}")
        VOICE = Voice()
    except Exception as e:
        LOAD_ERROR = repr(e)
        log.exception("voice failed to load")


def main():
    # Serve /health immediately; the model loads in the background.
    threading.Thread(target=_load, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    log.info("Matt voice server on 127.0.0.1:%d (loading model...)", PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
