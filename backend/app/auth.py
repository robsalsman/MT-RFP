"""Shared-password team gate.

When MTRFP_TEAM_PASSWORD is set (required before exposing the app over a
tunnel), every /api call except login/health must carry a valid bearer token.
Tokens are stateless HMAC-signed strings with an expiry — no session store.

When the password is unset (local dev), auth is disabled so the app runs
open on localhost.
"""
import hashlib
import hmac
import os
import time

TOKEN_TTL_SECONDS = int(os.environ.get("MTRFP_SESSION_TTL", str(7 * 24 * 3600)))


def team_password() -> str:
    return os.environ.get("MTRFP_TEAM_PASSWORD", "")


def auth_enabled() -> bool:
    return bool(team_password())


def _secret() -> bytes:
    # Explicit secret if provided; otherwise derive a stable one from the
    # password so tokens survive restarts without extra config.
    explicit = os.environ.get("MTRFP_AUTH_SECRET", "")
    if explicit:
        return explicit.encode()
    return ("derived-secret::" + team_password()).encode() or b"dev"


def check_password(password: str) -> bool:
    tp = team_password()
    return bool(tp) and hmac.compare_digest(password or "", tp)


def issue_token() -> str:
    exp = str(int(time.time()) + TOKEN_TTL_SECONDS)
    sig = hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify_token(token: str) -> bool:
    try:
        exp, sig = (token or "").split(".", 1)
    except ValueError:
        return False
    expected = hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        return int(exp) > time.time()
    except ValueError:
        return False


def bearer_from_header(header: str | None) -> str:
    if not header:
        return ""
    return header[7:].strip() if header.lower().startswith("bearer ") \
        else header.strip()
