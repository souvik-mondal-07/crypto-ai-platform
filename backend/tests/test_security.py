"""
Unit tests for app/core/security.py. No MongoDB, no HTTP — pure
crypto/logic.
"""

import pytest

from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_not_stored_plaintext():
    password_hash = hash_password("a-reasonable-password")
    assert password_hash != "a-reasonable-password"
    # Argon2 hashes are self-describing strings like $argon2id$v=19$...
    assert password_hash.startswith("$argon2")


def test_verify_password_accepts_correct_password():
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", password_hash) is True


def test_verify_password_rejects_incorrect_password():
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("wrong password", password_hash) is False


def test_verify_password_rejects_malformed_hash_without_raising():
    # Must never raise — a corrupted/legacy hash should just fail verification.
    assert verify_password("anything", "not-a-real-argon2-hash") is False


def test_same_password_produces_different_hashes():
    """Argon2 salts each hash — two hashes of the same password must differ."""
    hash_1 = hash_password("same-password")
    hash_2 = hash_password("same-password")
    assert hash_1 != hash_2
    assert verify_password("same-password", hash_1)
    assert verify_password("same-password", hash_2)


def test_create_and_decode_access_token_round_trip():
    token = create_access_token(subject="507f1f77bcf86cd799439011")
    payload = decode_access_token(token)
    assert payload["sub"] == "507f1f77bcf86cd799439011"
    assert "exp" in payload
    assert "iat" in payload


def test_access_token_never_contains_password_fields():
    token = create_access_token(subject="some-user-id")
    payload = decode_access_token(token)
    assert "password" not in payload
    assert "password_hash" not in payload
    assert "email" not in payload
    assert "name" not in payload


def test_expired_token_raises_token_expired_error():
    # A negative expiry means the token is already expired the instant
    # it's created.
    token = create_access_token(subject="some-user-id", expires_minutes=-1)
    with pytest.raises(TokenExpiredError):
        decode_access_token(token)


def test_malformed_token_raises_token_invalid_error():
    with pytest.raises(TokenInvalidError):
        decode_access_token("this.is.not-a-valid-jwt")


def test_token_signed_with_different_secret_is_invalid():
    from jose import jwt as jose_jwt

    bad_token = jose_jwt.encode({"sub": "x"}, "a-completely-different-secret", algorithm="HS256")
    with pytest.raises(TokenInvalidError):
        decode_access_token(bad_token)
