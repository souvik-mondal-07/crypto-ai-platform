"""
Unit tests for auth Pydantic schemas — email normalization/validation,
password confirmation matching. No MongoDB, no HTTP.
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest


def test_register_request_accepts_matching_passwords():
    req = RegisterRequest(
        name="Test User", email="test@example.com",
        password="password123", confirm_password="password123",
    )
    assert req.password == "password123"


def test_register_request_rejects_mismatched_passwords():
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="Test User", email="test@example.com",
            password="password123", confirm_password="different456",
        )


def test_register_request_rejects_invalid_email_format():
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="Test User", email="not-an-email",
            password="password123", confirm_password="password123",
        )


def test_register_request_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="Test User", email="test@example.com",
            password="short", confirm_password="short",
        )


def test_register_request_rejects_blank_name():
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="   ", email="test@example.com",
            password="password123", confirm_password="password123",
        )


def test_register_request_trims_name_whitespace():
    req = RegisterRequest(
        name="  Test User  ", email="test@example.com",
        password="password123", confirm_password="password123",
    )
    assert req.name == "Test User"
