"""Profile, change-password and settings endpoints (Phase 16). The user comes from the JWT only."""

from typing import Any

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.schemas.profile import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    SettingsResponse,
    SettingsUpdateRequest,
)
from app.services.profile_service import ProfileService
from app.services.user_feature_common import user_object_id

router = APIRouter(prefix="/profile", tags=["Profile"])
settings_router = APIRouter(prefix="/settings", tags=["Settings"])


def _service() -> ProfileService:
    return ProfileService()


@router.get("", response_model=ProfileResponse)
async def get_profile(current_user: dict[str, Any] = Depends(get_current_user)) -> ProfileResponse:
    return await _service().get_profile(current_user)


@router.put("", response_model=ProfileResponse)
async def update_profile(payload: ProfileUpdateRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> ProfileResponse:
    """Updates the display name only. Email is read-only in this phase."""
    return await _service().update_profile(user_object_id(current_user), payload)


@router.post("/password", response_model=ChangePasswordResponse)
async def change_password(
    payload: ChangePasswordRequest, current_user: dict[str, Any] = Depends(get_current_user)
) -> ChangePasswordResponse:
    """Verifies the CURRENT password, then stores the new one as an Argon2 hash. 400 CURRENT_PASSWORD_INCORRECT otherwise."""
    return await _service().change_password(current_user, payload)


@settings_router.get("", response_model=SettingsResponse)
async def get_settings(current_user: dict[str, Any] = Depends(get_current_user)) -> SettingsResponse:
    return await _service().get_settings(user_object_id(current_user))


@settings_router.put("", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdateRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> SettingsResponse:
    return await _service().update_settings(user_object_id(current_user), payload)
