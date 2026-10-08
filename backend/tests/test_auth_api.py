"""
API-level tests for /api/v1/auth/*, with AuthService/get_current_user
mocked — no MongoDB required. Verifies routing, request validation,
response shape, and that no sample/hard-coded user ever appears.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.schemas.auth import AuthResponse, RegisterResponse, TokenResponse, UserResponse


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _user_response(**overrides):
    data = dict(
        id="507f1f77bcf86cd799439011",
        name="Test User",
        email="test@example.com",
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    data.update(overrides)
    return UserResponse(**data)


def test_register_rejects_mismatched_passwords_with_422(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test User", "email": "test@example.com",
            "password": "password123", "confirm_password": "different456",
        },
    )
    assert response.status_code == 422


def test_register_success_returns_user_never_password(client):
    with patch("app.api.v1.auth.AuthService") as mock_service_cls:
        instance = mock_service_cls.return_value
        instance.register = AsyncMock(return_value=RegisterResponse(user=_user_response()))
        response = client.post(
            "/api/v1/auth/register",
            json={
                "name": "Test User", "email": "test@example.com",
                "password": "password123", "confirm_password": "password123",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["name"] == "Test User"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]
    assert "confirm_password" not in body


def test_register_duplicate_email_returns_consistent_error_shape(client):
    with patch("app.api.v1.auth.AuthService") as mock_service_cls:
        instance = mock_service_cls.return_value
        instance.register = AsyncMock(
            side_effect=AppError(409, "AUTH_EMAIL_EXISTS", "An account with this email already exists.")
        )
        response = client.post(
            "/api/v1/auth/register",
            json={
                "name": "Test User", "email": "dup@example.com",
                "password": "password123", "confirm_password": "password123",
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AUTH_EMAIL_EXISTS"


def test_login_success_returns_token_and_actual_user(client):
    with patch("app.api.v1.auth.AuthService") as mock_service_cls:
        instance = mock_service_cls.return_value
        instance.login = AsyncMock(
            return_value=AuthResponse(
                user=_user_response(name="Real Registered Name"),
                token=TokenResponse(access_token="a.b.c", expires_in_minutes=60),
            )
        )
        response = client.post(
            "/api/v1/auth/login", json={"email": "test@example.com", "password": "password123"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["name"] == "Real Registered Name"
    assert body["token"]["access_token"] == "a.b.c"
    # Never a hard-coded sample name.
    assert body["user"]["name"] != "Demo User"


def test_login_invalid_credentials_returns_generic_error(client):
    with patch("app.api.v1.auth.AuthService") as mock_service_cls:
        instance = mock_service_cls.return_value
        instance.login = AsyncMock(
            side_effect=AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid email or password.")
        )
        response = client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
        )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    assert body["error"]["message"] == "Invalid email or password."


def test_me_without_token_returns_401(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_TOKEN"


def test_me_with_invalid_token_returns_401(client):
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_TOKEN"


def test_me_with_valid_token_returns_actual_user_not_sample(client):
    from bson import ObjectId

    from app.core.security import create_access_token

    user_id = str(ObjectId())
    token = create_access_token(subject=user_id)
    user_doc = {
        "_id": ObjectId(user_id),
        "name": "Uniquely Registered Person",
        "email": "unique@example.com",
        "password_hash": "$argon2id$fake",
        "is_active": True,
        "role": "user",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch("app.core.dependencies.UserRepository") as mock_repo_cls:
        mock_repo_cls.return_value.find_by_id = AsyncMock(return_value=user_doc)
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Uniquely Registered Person"
    assert body["email"] == "unique@example.com"
    assert "password_hash" not in body
    assert body["name"] not in ("John Doe", "Demo User", "Sample User", "Guest User", "Test User")


def test_logout_returns_success_message(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


def test_market_routes_still_work_after_auth_added(client):
    """Step 4 must not break Step 3's market endpoints."""
    with patch("app.api.v1.coins.CoinService") as mock_service_cls:
        from app.schemas.coin import CoinListResponse

        instance = mock_service_cls.return_value
        instance.list_coins = AsyncMock(
            return_value=CoinListResponse(items=[], page=1, limit=100, total=0, pages=0)
        )
        response = client.get("/api/v1/coins")
    assert response.status_code == 200
