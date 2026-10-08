"""
Authentication service — registration and login business logic.

Routes call this, never the repository or security utilities directly.
"""

from typing import Optional

from app.config import get_settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import EmailAlreadyExistsError, UserRepository
from app.schemas.auth import AuthResponse, RegisterResponse, TokenResponse
from app.schemas.converters import user_doc_to_schema

# Deliberately generic — never reveals whether the email exists, was
# the wrong password, or anything else account-specific. Same message
# for every login failure reason.
INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."


class AuthService:
    def __init__(self, user_repository: Optional[UserRepository] = None) -> None:
        self._users = user_repository or UserRepository()

    async def register(self, *, name: str, email: str, password: str) -> RegisterResponse:
        """
        `confirm_password` is validated at the schema boundary
        (`RegisterRequest.passwords_match`) and never reaches this
        method or the database — only `password` (already confirmed
        equal) is hashed and stored.
        """
        if await self._users.email_exists(email):
            raise AppError(409, "AUTH_EMAIL_EXISTS", "An account with this email already exists.")

        password_hash = hash_password(password)
        try:
            user_doc = await self._users.create_user(name=name, email=email, password_hash=password_hash)
        except EmailAlreadyExistsError:
            # Covers the race between the email_exists() check above
            # and this insert — the unique index is the real guarantee,
            # this is just translating its failure into a clean error.
            raise AppError(409, "AUTH_EMAIL_EXISTS", "An account with this email already exists.")

        return RegisterResponse(user=user_doc_to_schema(user_doc))

    async def login(self, *, email: str, password: str) -> AuthResponse:
        user_doc = await self._users.find_by_email(email)

        # Same generic error whether the email doesn't exist or the
        # password is wrong — never reveal which one it was.
        if user_doc is None or not verify_password(password, user_doc["password_hash"]):
            raise AppError(401, "AUTH_INVALID_CREDENTIALS", INVALID_CREDENTIALS_MESSAGE)

        if not user_doc.get("is_active", True):
            raise AppError(403, "AUTH_USER_INACTIVE", "This account is inactive.")

        access_token = create_access_token(subject=str(user_doc["_id"]))
        settings = get_settings()

        return AuthResponse(
            user=user_doc_to_schema(user_doc),
            token=TokenResponse(
                access_token=access_token,
                expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            ),
        )
