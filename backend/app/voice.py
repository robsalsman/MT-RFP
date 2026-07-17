"""Voice layer via NVIDIA-hosted Riva speech services (same NVIDIA API key
as Nemotron):

- Speech-to-text: Parakeet ASR  (grpc.nvcf.nvidia.com, offline recognize)
- Text-to-speech: Magpie TTS multilingual

Together with the Nemotron chat loop this gives speech -> assistant ->
speech. Audio in must be 16-bit mono WAV (the frontend records exactly
that); audio out is 22.05 kHz 16-bit mono WAV.
"""
import io
import logging
import os
import re
import wave

from . import config

log = logging.getLogger(__name__)

NVCF_GRPC = os.environ.get("NVIDIA_SPEECH_GRPC", "grpc.nvcf.nvidia.com:443")
ASR_FUNCTION_ID = os.environ.get(
    "NVIDIA_ASR_FUNCTION_ID", "d3fe9151-442b-4204-a70d-5fcc597fd610")
TTS_FUNCTION_ID = os.environ.get(
    "NVIDIA_TTS_FUNCTION_ID", "877104f7-e885-42b9-8de8-f6e4c6303969")
TTS_VOICE = os.environ.get("NVIDIA_TTS_VOICE",
                           "Magpie-Multilingual.EN-US.Sofia")
TTS_SAMPLE_RATE = 22050
# Magpie enforces a 400-token sequence cap; dense text (numbers, IDs) can
# expand to ~2 tokens/char, so keep chunks short.
TTS_CHUNK_CHARS = 180


def available() -> bool:
    return bool(config.NEMOTRON_API_KEY)


def _auth(function_id: str):
    import riva.client
    return riva.client.Auth(
        uri=NVCF_GRPC, use_ssl=True,
        metadata_args=[["function-id", function_id],
                       ["authorization",
                        f"Bearer {config.NEMOTRON_API_KEY}"]])


def transcribe(wav_bytes: bytes) -> str:
    """16-bit mono WAV bytes -> transcript text."""
    import riva.client
    asr = riva.client.ASRService(_auth(ASR_FUNCTION_ID))
    cfg = riva.client.RecognitionConfig(
        language_code="en-US", max_alternatives=1,
        enable_automatic_punctuation=True)
    resp = asr.offline_recognize(wav_bytes, cfg)
    return " ".join(r.alternatives[0].transcript
                    for r in resp.results).strip()


def synthesize(text: str) -> bytes:
    """Text -> WAV bytes. Long text is split at sentence boundaries into
    <=~320-char chunks (Magpie per-request cap) and the PCM concatenated."""
    import riva.client
    from riva.client.proto.riva_audio_pb2 import AudioEncoding
    tts = riva.client.SpeechSynthesisService(_auth(TTS_FUNCTION_ID))
    pcm = b""
    for chunk in _chunks(_speakable(text)):
        try:
            resp = tts.synthesize(chunk, TTS_VOICE, "en-US",
                                  sample_rate_hz=TTS_SAMPLE_RATE,
                                  encoding=AudioEncoding.LINEAR_PCM)
            pcm += resp.audio
        except Exception as e:  # skip an unspeakable chunk, keep the rest
            log.warning("TTS chunk failed (%d chars): %s", len(chunk), e)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TTS_SAMPLE_RATE)
        wf.writeframesraw(pcm)
    return buf.getvalue()


def _speakable(text: str) -> str:
    """Strip markdown that reads terribly aloud (tables, emphasis, code)."""
    lines = []
    for line in (text or "").splitlines():
        s = line.strip()
        if re.fullmatch(r"\|?[\s|:-]+\|?", s):  # table separator rows
            continue
        if s.startswith("|") or s.count("|") >= 2:  # table row -> phrase
            cells = [c.strip() for c in s.strip("|").split("|") if c.strip()]
            s = ", ".join(cells) + "."
        s = re.sub(r"[*_`#>]+", "", s)
        if s:
            lines.append(s)
    return " ".join(lines)


def _chunks(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?;])\s+", text)
    chunks, cur = [], ""
    for s in sentences:
        while len(s) > TTS_CHUNK_CHARS:  # pathological run-on
            chunks.append(s[:TTS_CHUNK_CHARS])
            s = s[TTS_CHUNK_CHARS:]
        if len(cur) + len(s) + 1 > TTS_CHUNK_CHARS and cur:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks
