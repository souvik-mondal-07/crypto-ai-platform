"""
Unit tests for get_current_user (app/core/dependencies.py) using a
fake UserRepository patched in — no MongoDB required.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.core.dependencies import get_current_user


def _user_doc(**overrides):
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "name": "Test User",
        "email": "test@example.com",
        "password_hash": "$argon2id$fake",
        "is_active": True,
        "role": "user",
        "created_at": now,
        "updated_at": now,
    }
    doc.update(overrides)
    return doc


class _FakeCredentials:
    def __init__(self, token: str):
        self.credentials = token


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials_raises_401():
    with pytest.raises(AppError) as exc_info:
        await get_current_user(credentials=None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "AUTH_INVALID_TOKEN"


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises_401():
    with pytest.raises(AppError) as exc_info:
        await get_current_user(credentials=_FakeCredentials("not-a-real-token"))
    assert exc_info.value.code == "AUTH_INVALID_TOKEN"


@pytest.mark.asyncio
async def test_get_current_user_expired_token_raises_distinct_code():
    token = create_access_token(subject=str(ObjectId()), expires_minutes=-1)
    with pytest.raises(AppError) as exc_info:
        await get_current_user(credentials=_FakeCredentials(token))
    assert exc_info.value.code == "AUTH_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_get_current_user_valid_token_returns_actual_user_doc():
    user_doc = _user_doc()
    token = create_access_token(subject=str(user_doc["_id"]))

    with patch("app.core.dependencies.UserRepository") as mock_repo_cls:
        mock_repo_cls.return_value.find_by_id = AsyncMock(return_value=user_doc)
        result = await get_current_user(credentials=_FakeCredentials(token))

    assert result["_id"] == user_doc["_id"]
    assert result["name"] == "Test User"


@pytest.mark.asyncio
async def test_get_current_user_user_not_found_raises_401():
    token = create_access_token(subject=str(ObjectId()))

    with patch("app.core.dependencies.UserRepository") as mock_repo_cls:
        mock_repo_cls.return_value.find_by_id = AsyncMock(return_value=None)
        with pytest.raises(AppError) as exc_info:
            await get_current_user(credentials=_FakeCredentials(token))
    assert exc_info.value.code == "AUTH_INVALID_TOKEN"


@pytest.mark.asyncio
async def test_get_current_user_inactive_user_raises_403():
    user_doc = _user_doc(is_active=False)
    token = create_access_token(subject=str(user_doc["_id"]))

    with patch("app.core.dependencies.UserRepository") as mock_repo_cls:
        mock_repo_cls.return_value.find_by_id = AsyncMock(return_value=user_doc)
        with pytest.raises(AppError) as exc_info:
            await get_current_user(credentials=_FakeCredentials(token))
    assert exc_info.value.code == "AUTH_USER_INACTIVE"
    assert exc_info.value.status_code == 403
