"""
Integration tests for the full authentication flow against a real
MongoDB instance. Skipped automatically if MongoDB isn't reachable —
same pattern as tests/test_database.py and
tests/test_market_data_integration.py.

Each test creates its own uniquely-emailed user and cleans it up
afterward — safe to run against a shared development database, never
touches unrelated documents.
"""

import uuid
from datetime import datetime, timezone

import pytest
from pymongo.errors import PyMongoError

from app.database import client as db_client
from app.database.database import get_database
from app.database.indexes import initialize_indexes
from app.repositories.user_repository import EmailAlreadyExistsError, UserRepository
from app.services.auth_service import AuthService
from app.core.exceptions import AppError
from app.core.security import verify_password


async def _mongodb_reachable() -> bool:
    try:
        test_client = db_client.create_client()
        await test_client.admin.command("ping")
        await test_client.close()
        return True
    except PyMongoError:
        return False


@pytest.fixture
async def connected_db():
    if not await _mongodb_reachable():
        pytest.skip("MongoDB is not reachable at the configured MONGODB_URI.")
    await db_client.connect()
    await initialize_indexes(get_database())
    yield
    await db_client.disconnect()


def _unique_email() -> str:
    return f"step4-test-{uuid.uuid4().hex[:12]}@example.com"


async def _cleanup(repo: UserRepository, email: str):
    doc = await repo.find_by_email(email)
    if doc:
        await repo.collection.delete_one({"_id": doc["_id"]})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_register_login_me_flow(connected_db):
    repo = UserRepository()
    service = AuthService(user_repository=repo)
    email = _unique_email()

    try:
        register_result = await service.register(name="Step4 Integration User", email=email, password="a-real-password")
        assert register_result.user.email == email
        assert register_result.user.name == "Step4 Integration User"

        login_result = await service.login(email=email, password="a-real-password")
        assert login_result.user.email == email
        assert login_result.token.access_token

        # Verify what's ACTUALLY in MongoDB — not just what the service returned.
        stored = await repo.find_by_email(email)
        assert stored["name"] == "Step4 Integration User"
        assert stored["email"] == email
        assert stored["is_active"] is True
        assert stored["role"] == "user"
        assert "created_at" in stored
        assert "updated_at" in stored

        # The critical security assertions from the spec:
        assert "password" not in stored
        assert "confirm_password" not in stored
        assert stored["password_hash"] != "a-real-password"
        assert verify_password("a-real-password", stored["password_hash"])
    finally:
        await _cleanup(repo, email)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_email_enforced_by_database_index(connected_db):
    """
    The unique index — not just the application-level pre-check — must
    reject a duplicate. Bypasses AuthService's email_exists() check by
    inserting twice directly through the repository to prove the index
    itself is the real guarantee.
    """
    repo = UserRepository()
    email = _unique_email()

    try:
        await repo.create_user(name="First", email=email, password_hash="$argon2id$fakehash1")
        with pytest.raises(EmailAlreadyExistsError):
            await repo.create_user(name="Second", email=email, password_hash="$argon2id$fakehash2")
    finally:
        await _cleanup(repo, email)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_normalization_prevents_case_variant_duplicates(connected_db):
    repo = UserRepository()
    service = AuthService(user_repository=repo)
    base_email = _unique_email()
    variant_email = base_email.upper()

    try:
        await service.register(name="First", email=base_email, password="password123")
        with pytest.raises(AppError) as exc_info:
            await service.register(name="Second", email=variant_email, password="password456")
        assert exc_info.value.code == "AUTH_EMAIL_EXISTS"
    finally:
        await _cleanup(repo, base_email)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_fails_for_inactive_user_end_to_end(connected_db):
    repo = UserRepository()
    service = AuthService(user_repository=repo)
    email = _unique_email()

    try:
        await service.register(name="Inactive User", email=email, password="password123")
        stored = await repo.find_by_email(email)
        await repo.collection.update_one({"_id": stored["_id"]}, {"$set": {"is_active": False}})

        with pytest.raises(AppError) as exc_info:
            await service.login(email=email, password="password123")
        assert exc_info.value.code == "AUTH_USER_INACTIVE"
    finally:
        await _cleanup(repo, email)
