"""
Authentication endpoints. All business logic lives in AuthService —
routes only handle HTTP concerns.
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from app.schemas.converters import user_doc_to_schema
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def _service() -> AuthService:
    return AuthService()


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(payload: RegisterRequest) -> RegisterResponse:
    """
    `confirm_password` is validated by the request schema and never
    stored. Returns the created user (never the password/password
    hash) — the client is expected to redirect to /login and
    authenticate normally (see docs/authentication.md for why V1
    doesn't auto-login after registration).
    """
    return await _service().register(name=payload.name, email=payload.email, password=payload.password)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    """Returns a JWT access token AND the actual authenticated user in one response."""
    return await _service().login(email=payload.email, password=payload.password)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> UserResponse:
    """
    The single source of truth for "who is the authenticated user".
    Always reflects the actual MongoDB document for the token's
    subject — never a cached, sample, or hard-coded value.
    """
    return user_doc_to_schema(current_user)


@router.post("/logout", response_model=LogoutResponse)
async def logout() -> LogoutResponse:
    """
    With stateless JWTs and no server-side revocation store (not
    implemented in V1 — see docs/authentication.md), this endpoint
    cannot itself invalidate an already-issued token. It exists as a
    consistent API contract; the actual logout is the frontend
    discarding its stored token and auth state.
    """
    return LogoutResponse()
