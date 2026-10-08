"""
Reusable FastAPI authentication dependency.

`get_current_user` is the ONLY place that extracts/validates the
Authorization header — every protected route depends on this rather
than duplicating JWT verification logic.
"""

from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AppError
from app.core.security import TokenExpiredError, TokenInvalidError, decode_access_token
from app.repositories.user_repository import UserRepository

# auto_error=False so a missing header produces our own consistent
# AppError/JSON shape rather than FastAPI's default 403 HTTPException
# shape.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """
    1. Extract the Authorization header (via HTTPBearer).
    2. Validate it's a Bearer token.
    3. Decode the JWT.
    4. Retrieve the user from MongoDB.
    5. Verify the user is active.
    6. Return the current user document.

    Never logs the token or the Authorization header. Raises a clean
    `AppError` (never a raw exception) for every failure mode.
    """
    if credentials is None or not credentials.credentials:
        raise AppError(401, "AUTH_INVALID_TOKEN", "Authentication required.")

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "Your session has expired. Please log in again.")
    except TokenInvalidError:
        raise AppError(401, "AUTH_INVALID_TOKEN", "Invalid authentication token.")

    user_id = payload.get("sub")
    if not user_id:
        raise AppError(401, "AUTH_INVALID_TOKEN", "Invalid authentication token.")

    users = UserRepository()
    user_doc = await users.find_by_id(user_id)
    if user_doc is None:
        raise AppError(401, "AUTH_INVALID_TOKEN", "Invalid authentication token.")

    if not user_doc.get("is_active", True):
        raise AppError(403, "AUTH_USER_INACTIVE", "This account is inactive.")

    return user_doc
