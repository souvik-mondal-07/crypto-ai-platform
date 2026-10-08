"""Pydantic models for authentication endpoints."""

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Reasonable, not arbitrarily restrictive: a minimum length only. No
# forced uppercase/symbol/digit requirements — those measurably don't
# improve real-world password strength and make development/testing
# needlessly annoying (see NIST SP 800-63B's guidance against
# composition rules).
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    confirm_password: str = Field(..., min_length=1, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name must not be blank.")
        return stripped

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=MAX_PASSWORD_LENGTH)


class UserResponse(BaseModel):
    """
    Safe, public-facing user representation. Never includes
    `password_hash` or any other internal security field.
    """

    id: str
    name: str
    email: str
    role: str
    created_at: datetime


class RegisterResponse(BaseModel):
    user: UserResponse
    message: str = "Registration successful"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class AuthResponse(BaseModel):
    """Login response: token + the actual authenticated user, in one call."""

    user: UserResponse
    token: TokenResponse


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"
