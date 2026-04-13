"""Unit tests for app.core.security."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.core.exceptions import Unauthorized
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_bcrypt_hash() -> None:
    hashed = hash_password("correct horse")
    # bcrypt hashes start with $2b$ (or $2a$/$2y$) and are 60 chars long
    assert hashed.startswith("$2")
    assert len(hashed) == 60


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("correct horse")
    assert verify_password("correct horse", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse")
    assert verify_password("battery staple", hashed) is False


def test_hash_password_is_salted_unique() -> None:
    """Same plaintext should produce different hashes (bcrypt salts)."""
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_create_access_token_contains_expected_claims() -> None:
    token = create_access_token(subject="owner")
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["sub"] == "owner"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_create_access_token_includes_extra_claims() -> None:
    token = create_access_token(subject="owner", extra={"role": "admin"})
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["role"] == "admin"
    assert payload["sub"] == "owner"


def test_decode_token_returns_payload_on_valid_token() -> None:
    token = create_access_token(subject="owner")
    payload = decode_token(token)
    assert payload["sub"] == "owner"


def test_decode_token_rejects_invalid_signature() -> None:
    # Use a 32-byte secret so jwt.encode does not raise InsecureKeyLengthWarning,
    # but the signature will still be invalid when decoded with the real secret.
    bad_token = jwt.encode(
        {"sub": "owner", "iat": int(datetime.now(UTC).timestamp())},
        "wrong_secret_that_is_long_enough_32b",
        algorithm=get_settings().jwt_algorithm,
    )
    with pytest.raises(Unauthorized):
        decode_token(bad_token)


def test_decode_token_rejects_expired_token() -> None:
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(hours=1)
    expired_token = jwt.encode(
        {
            "sub": "owner",
            "iat": int((past - timedelta(hours=1)).timestamp()),
            "exp": int(past.timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(Unauthorized):
        decode_token(expired_token)


def test_decode_token_rejects_malformed_token() -> None:
    with pytest.raises(Unauthorized):
        decode_token("not.a.valid.jwt")
