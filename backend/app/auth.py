"""Per-user name + PIN gate.

Each rep signs in with a username and a 4-digit PIN. Credentials live in
data/users.json (gitignored — never committed); PINs are stored hashed. A
successful login returns a stateless HMAC-signed token that carries the
username, so the app (and Matt, the assistant) can greet people by name.

When no users exist, auth is disabled so the app runs open on localhost.
"""
import hashlib
import hmac
import json
import os
import re
import time

from . import config

TOKEN_TTL_SECONDS = int(os.environ.get("MTRFP_SESSION_TTL", str(7 * 24 * 3600)))
USERS_PATH = config.DATA_DIR / "users.json"
_USERNAME_RE = re.compile(r"[^a-z0-9_]")


def _secret() -> bytes:
    """Stable per-install signing secret. Explicit env wins; otherwise a
    random secret is generated once and cached under data/ so tokens and PIN
    hashes stay valid across restarts."""
    explicit = os.environ.get("MTRFP_AUTH_SECRET", "")
    if explicit:
        return explicit.encode()
    path = config.DATA_DIR / ".auth_secret"
    if path.exists():
        return path.read_bytes()
    secret = os.urandom(32)
    path.write_bytes(secret)
    return secret


def normalize_username(username: str) -> str:
    return _USERNAME_RE.sub("", (username or "").strip().lower())


def load_users() -> dict:
    if USERS_PATH.exists():
        try:
            return json.loads(USERS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _hash_pin(username: str, pin: str) -> str:
    return hmac.new(_secret(), f"{username}:{pin}".encode(),
                    hashlib.sha256).hexdigest()


def add_user(username: str, display_name: str, pin: str) -> dict:
    """Create/replace a user. PIN must be exactly 4 digits."""
    username = normalize_username(username)
    if not username:
        raise ValueError("username must contain letters or digits")
    if not re.fullmatch(r"\d{4}", pin or ""):
        raise ValueError("PIN must be exactly 4 digits")
    users = load_users()
    users[username] = {"display_name": (display_name or username).strip(),
                       "pin_hash": _hash_pin(username, pin)}
    USERS_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")
    return users[username]


def remove_user(username: str) -> None:
    users = load_users()
    if users.pop(normalize_username(username), None) is not None:
        USERS_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")


def auth_enabled() -> bool:
    return bool(load_users())


def verify_credentials(username: str, pin: str) -> str | None:
    """Returns display_name on success, else None."""
    username = normalize_username(username)
    user = load_users().get(username)
    if not user:
        return None
    if hmac.compare_digest(user.get("pin_hash", ""),
                           _hash_pin(username, pin or "")):
        return user.get("display_name", username)
    return None


def issue_token(username: str) -> str:
    username = normalize_username(username)
    exp = str(int(time.time()) + TOKEN_TTL_SECONDS)
    payload = f"{username}.{exp}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token: str) -> str | None:
    """Returns the username if the token is valid and the user still exists."""
    try:
        username, exp, sig = (token or "").split(".", 2)
    except ValueError:
        return None
    expected = hmac.new(_secret(), f"{username}.{exp}".encode(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        if int(exp) <= time.time():
            return None
    except ValueError:
        return None
    return username if username in load_users() else None


def display_name(username: str | None) -> str | None:
    if not username:
        return None
    user = load_users().get(username)
    return user.get("display_name") if user else None


def bearer_from_header(header: str | None) -> str:
    if not header:
        return ""
    return header[7:].strip() if header.lower().startswith("bearer ") \
        else header.strip()


def user_from_header(header: str | None) -> tuple[str | None, str | None]:
    """(username, display_name) for a request's Authorization header."""
    username = verify_token(bearer_from_header(header))
    return username, display_name(username)
