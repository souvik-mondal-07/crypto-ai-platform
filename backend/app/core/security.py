"""
Centralized security-sensitive logic: password hashing (Argon2) and
JWT creation/decoding. Nothing outside this module should call
`argon2` or `jose`/`jwt` directly — this keeps every password/token
operation auditable in one place.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import get_settings

logger = logging.getLogger("crypto_ai_platform.security")


class TokenExpiredError(Exception):
    """The token's signature is valid but it has expired."""


class TokenInvalidError(Exception):
    """The token is malformed, has a bad signature, or is otherwise unusable."""


# Argon2id (the default argon2-cffi profile) with library defaults,
# which already meet OWASP's current minimum recommendation
# (m=19456 KiB, t=2, p=1) for interactive password hashing. Not
# tuned further for Step 4 — revisit only with real production
# hardware/latency numbers, not guessed.
_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash a password with Argon2. Never store the plaintext anywhere, including logs."""
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verify a password against its Argon2 hash. Returns False on any
    mismatch or malformed-hash condition — never raises, so callers
    don't need to special-case Argon2's exception types.
    """
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """
    True if this hash was made with older/weaker parameters than the
    current hasher uses — lets a future login flow silently upgrade a
    user's stored hash. Not wired into the login flow itself in Step 4
    (no reason to add complexity before any hash has ever aged), but
    kept available so that follow-up work doesn't need a new module.
    """
    return _password_hasher.check_needs_rehash(password_hash)


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """
    Create a JWT access token. Claims are intentionally minimal — only
    `sub` (user ID), `iat`, and `exp`. Never put a password, password
    hash, or full user profile in a JWT: it's not encrypted, only
    signed, so anything inside it is readable by whoever holds the
    token.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire_minutes = expires_minutes if expires_minutes is not None else settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Raises `TokenExpiredError` if the signature is valid but the token
    has expired, or `TokenInvalidError` for any other failure
    (malformed, wrong signature, wrong algorithm, missing claims).
    Never logs the token itself.
    """
    settings = get_settings()
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except JWTError as exc:
        raise TokenInvalidError() from exc
