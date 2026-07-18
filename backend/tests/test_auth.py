"""Team-password gate: token issue/verify and password check."""
import time

from app import auth


def test_auth_disabled_without_password(monkeypatch):
    monkeypatch.delenv("MTRFP_TEAM_PASSWORD", raising=False)
    assert auth.auth_enabled() is False


def test_auth_enabled_with_password(monkeypatch):
    monkeypatch.setenv("MTRFP_TEAM_PASSWORD", "secret")
    assert auth.auth_enabled() is True


def test_password_check(monkeypatch):
    monkeypatch.setenv("MTRFP_TEAM_PASSWORD", "secret")
    assert auth.check_password("secret") is True
    assert auth.check_password("wrong") is False
    assert auth.check_password("") is False


def test_token_roundtrip(monkeypatch):
    monkeypatch.setenv("MTRFP_TEAM_PASSWORD", "secret")
    monkeypatch.delenv("MTRFP_AUTH_SECRET", raising=False)
    token = auth.issue_token()
    assert auth.verify_token(token) is True
    assert auth.verify_token("garbage") is False
    assert auth.verify_token(token + "x") is False


def test_token_rejected_after_password_change(monkeypatch):
    # tokens are signed with a secret derived from the password, so changing
    # the password invalidates outstanding sessions.
    monkeypatch.setenv("MTRFP_TEAM_PASSWORD", "secret")
    monkeypatch.delenv("MTRFP_AUTH_SECRET", raising=False)
    token = auth.issue_token()
    monkeypatch.setenv("MTRFP_TEAM_PASSWORD", "changed")
    assert auth.verify_token(token) is False


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setenv("MTRFP_TEAM_PASSWORD", "secret")
    monkeypatch.delenv("MTRFP_AUTH_SECRET", raising=False)
    monkeypatch.setattr(auth, "TOKEN_TTL_SECONDS", -1)
    token = auth.issue_token()
    assert auth.verify_token(token) is False


def test_bearer_parsing():
    assert auth.bearer_from_header("Bearer abc") == "abc"
    assert auth.bearer_from_header("abc") == "abc"
    assert auth.bearer_from_header(None) == ""
