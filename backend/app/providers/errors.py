"""
Common error types for market-data providers.

Provider clients raise these instead of leaking raw httpx exceptions
into the service layer, so services can handle "provider is down" the
same way regardless of which provider it was.
"""


class ProviderError(Exception):
    """Base class for all provider-related failures."""


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the configured timeout."""


class ProviderRateLimitError(ProviderError):
    """The provider responded with 429 Too Many Requests."""


class ProviderUnavailableError(ProviderError):
    """The provider responded with a 5xx error, or the connection failed."""


class ProviderResponseError(ProviderError):
    """The provider responded with 2xx but the payload was malformed/unexpected."""


class ProviderNotFoundError(ProviderResponseError):
    """
    The provider responded 404 — it does not know this resource. A
    subclass of ProviderResponseError so every existing handler/test
    that expects a 4xx to surface as ProviderResponseError still holds.
    """
