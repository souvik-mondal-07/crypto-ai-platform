"""Profile, change-password and settings logic (Phase 16). Always acts on the authenticated user only."""

import logging
from typing import Any, Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.converters import user_doc_to_schema
from app.schemas.profile import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    NotificationSettings,
    ProfileResponse,
    ProfileUpdateRequest,
    SettingsResponse,
    SettingsUpdateRequest,
)

logger = logging.getLogger("crypto_ai_platform.services.profile")


def _profile(doc: dict[str, Any]) -> ProfileResponse:
    user = user_doc_to_schema(doc)
    return ProfileResponse(**user.model_dump())


def settings_doc_to_response(raw: Optional[dict[str, Any]]) -> SettingsResponse:
    raw = raw or {}
    theme = raw.get("theme") if raw.get("theme") in ("light", "dark") else None
    notifications = raw.get("notifications") or {}
    return SettingsResponse(
        theme=theme,
        notifications=NotificationSettings(price_alerts=bool(notifications.get("price_alerts", True))),
    )


class ProfileService:
    def __init__(self, users: Optional[UserRepository] = None) -> None:
        self._users = users or UserRepository()

    async def get_profile(self, current_user: dict[str, Any]) -> ProfileResponse:
        return _profile(current_user)

    async def update_profile(self, user_id: ObjectId, request: ProfileUpdateRequest) -> ProfileResponse:
        doc = await self._users.update_name(user_id, request.name)
        if doc is None:
            raise AppError(404, "USER_NOT_FOUND", "User not found.")
        return _profile(doc)

    async def change_password(self, current_user: dict[str, Any], request: ChangePasswordRequest) -> ChangePasswordResponse:
        """
        The user is the one the JWT authenticated; the CURRENT password is re-verified against the
        stored Argon2 hash before anything changes, then the new password is hashed with Argon2.
        The plaintext is never stored or logged.
        """
        if not verify_password(request.current_password, current_user["password_hash"]):
            raise AppError(400, "CURRENT_PASSWORD_INCORRECT", "Your current password is incorrect.")
        if not await self._users.update_password_hash(current_user["_id"], hash_password(request.new_password)):
            raise AppError(404, "USER_NOT_FOUND", "User not found.")
        logger.info("Password changed for user %s", current_user["_id"])
        return ChangePasswordResponse()

    async def get_settings(self, user_id: ObjectId) -> SettingsResponse:
        return settings_doc_to_response(await self._users.get_settings(user_id))

    async def update_settings(self, user_id: ObjectId, request: SettingsUpdateRequest) -> SettingsResponse:
        fields: dict[str, Any] = {}
        if "theme" in request.model_fields_set:
            fields["settings.theme"] = request.theme
        if request.notifications is not None and "price_alerts" in request.notifications.model_fields_set:
            if request.notifications.price_alerts is None:
                raise AppError(422, "INVALID_SETTING", "notifications.price_alerts cannot be null.")
            fields["settings.notifications.price_alerts"] = request.notifications.price_alerts
        if not fields:
            return await self.get_settings(user_id)
        updated = await self._users.update_settings(user_id, fields)
        if updated is None:
            raise AppError(404, "USER_NOT_FOUND", "User not found.")
        return settings_doc_to_response(updated)
