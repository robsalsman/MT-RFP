"""Per-user name + PIN gate: user store, credential check, token flow."""
import pytest

from app import auth


@pytest.fixture
def users_file(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setenv("MTRFP_AUTH_SECRET", "test-secret")
    return tmp_path / "users.json"


def test_auth_disabled_without_users(users_file):
    assert auth.auth_enabled() is False


def test_add_and_verify_user(users_file):
    auth.add_user("Kim", "Kim", "6969")
    assert auth.auth_enabled() is True
    assert auth.verify_credentials("kim", "6969") == "Kim"
    assert auth.verify_credentials("KIM", "6969") == "Kim"  # case-insensitive
    assert auth.verify_credentials("kim", "0000") is None
    assert auth.verify_credentials("nobody", "6969") is None


def test_pin_must_be_four_digits(users_file):
    for bad in ("123", "12345", "abcd", ""):
        with pytest.raises(ValueError):
            auth.add_user("x", "X", bad)


def test_token_carries_username(users_file):
    auth.add_user("kim", "Kim", "6969")
    token = auth.issue_token("kim")
    assert auth.verify_token(token) == "kim"
    assert auth.display_name("kim") == "Kim"
    assert auth.verify_token("garbage") is None
    assert auth.verify_token(token + "x") is None


def test_removed_user_token_invalid(users_file):
    auth.add_user("kim", "Kim", "6969")
    token = auth.issue_token("kim")
    auth.remove_user("kim")
    assert auth.verify_token(token) is None


def test_expired_token_rejected(users_file, monkeypatch):
    auth.add_user("kim", "Kim", "6969")
    monkeypatch.setattr(auth, "TOKEN_TTL_SECONDS", -1)
    assert auth.verify_token(auth.issue_token("kim")) is None


def test_user_from_header(users_file):
    auth.add_user("kim", "Kim", "6969")
    token = auth.issue_token("kim")
    assert auth.user_from_header(f"Bearer {token}") == ("kim", "Kim")
    assert auth.user_from_header(None) == (None, None)
