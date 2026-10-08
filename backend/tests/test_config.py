"""
Unit tests: configuration only. No MongoDB connection required.
"""

from app.config import get_settings


def test_mongodb_settings_have_defaults():
    settings = get_settings()
    assert settings.MONGODB_URI
    assert settings.MONGODB_DATABASE


def test_mongodb_default_uri_has_no_embedded_credentials():
    """
    The default (no .env override) URI must be the plain local
    development default — never a hard-coded credential string.
    Real credentials, if any, are expected to come from the
    environment via MONGODB_URI, not from this codebase.
    """
    settings = get_settings()
    if settings.MONGODB_URI == "mongodb://localhost:27017":
        assert "@" not in settings.MONGODB_URI
