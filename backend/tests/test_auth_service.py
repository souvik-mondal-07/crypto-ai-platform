"""
Unit tests for AuthService using an in-memory fake UserRepository —
no MongoDB required. Exercises registration, duplicate-email
handling, login success/failure, inactive-user handling, and confirms
no plaintext password or confirm_password ever reaches storage.
"""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.repositories.user_repository import EmailAlreadyExistsError, normalize_email
from app.services.auth_service import AuthService


class FakeUserRepository:
    def __init__(self):
        self.by_email: dict[str, dict] = {}

    async def email_exists(self, email: str) -> bool:
        return normalize_email(email) in self.by_email

    async def create_user(self, *, name: str, email: str, password_hash: str) -> dict:
        normalized = normalize_email(email)
        if normalized in self.by_email:
            raise EmailAlreadyExistsError()
        now = datetime.now(timezone.utc)
        doc = {
            "_id": ObjectId(),
            "name": name,
            "email": normalized,
            "password_hash": password_hash,
            "is_active": True,
            "role": "user",
            "created_at": now,
            "updated_at": now,
        }
        self.by_email[normalized] = doc
        return doc

    async def find_by_email(self, email: str):
        return self.by_email.get(normalize_email(email))


@pytest.mark.asyncio
async def test_register_creates_user_and_hashes_password():
    repo = FakeUserRepository()
    service = AuthService(user_repository=repo)

    result = await service.register(name="Test User", email="Test@Example.com", password="password123")

    assert result.user.name == "Test User"
    assert result.user.email == "test@example.com"  # normalized
    assert "password" not in result.model_dump()
    assert "password_hash" not in result.model_dump()

    stored = repo.by_email["test@example.com"]
    assert stored["password_hash"] != "password123"
    assert verify_password("password123", stored["password_hash"])


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email():
    repo = FakeUserRepository()
    service = AuthService(user_repository=repo)
    await service.register(name="First User", email="dup@example.com", password="password123")

    with pytest.raises(AppError) as exc_info:
        await service.register(name="Second User", email="dup@example.com", password="password456")
    assert exc_info.value.code == "AUTH_EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_register_treats_email_case_insensitively_for_duplicates():
    repo = FakeUserRepository()
    service = AuthService(user_repository=repo)
    await service.register(name="First User", email="dup@example.com", password="password123")

    with pytest.raises(AppError) as exc_info:
        await service.register(name="Second User", email="DUP@EXAMPLE.COM", password="password456")
    assert exc_info.value.code == "AUTH_EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_credentials():
    repo = FakeUserRepository()
    service = AuthService(user_repository=repo)
    await service.register(name="Test User", email="test@example.com", password="password123")

    result = await service.login(email="test@example.com", password="password123")
    assert result.user.email == "test@example.com"
    assert result.token.access_token
    assert result.token.token_type == "bearer"


@pytest.mark.asyncio
async def test_login_fails_with_wrong_password_generic_message():
    repo = FakeUserRepository()
    service = AuthService(user_repository=repo)
    await service.register(name="Test User", email="test@example.com", password="password123")

    with pytest.raises(AppError) as exc_info:
        await service.login(email="test@example.com", password="wrong-password")
    assert exc_info.value.code == "AUTH_INVALID_CREDENTIALS"
    assert exc_info.value.message == "Invalid email or password."


@pytest.mark.asyncio
async def test_login_fails_for_nonexistent_email_with_same_generic_message():
    repo = FakeUserRepository()
    service = AuthService(user_repository=repo)

    with pytest.raises(AppError) as exc_info:
        await service.login(email="nobody@example.com", password="whatever123")
    assert exc_info.value.code == "AUTH_INVALID_CREDENTIALS"
    assert exc_info.value.message == "Invalid email or password."


@pytest.mark.asyncio
async def test_login_fails_for_inactive_user():
    repo = FakeUserRepository()
    service = AuthService(user_repository=repo)
    await service.register(name="Test User", email="inactive@example.com", password="password123")
    repo.by_email["inactive@example.com"]["is_active"] = False

    with pytest.raises(AppError) as exc_info:
        await service.login(email="inactive@example.com", password="password123")
    assert exc_info.value.code == "AUTH_USER_INACTIVE"


@pytest.mark.asyncio
async def test_login_token_subject_is_user_id():
    from app.core.security import decode_access_token

    repo = FakeUserRepository()
    service = AuthService(user_repository=repo)
    await service.register(name="Test User", email="test@example.com", password="password123")

    result = await service.login(email="test@example.com", password="password123")
    payload = decode_access_token(result.token.access_token)
    assert payload["sub"] == result.user.id
