"""Pydantic models for /api/v1/profile and /api/v1/settings (Phase 16)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.auth import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH


class ProfileResponse(BaseModel):
    """Never includes password_hash or any other internal security field."""

    id: str
    name: str
    email: str
    role: str
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    """Only the display name is editable. Email is deliberately not (see docs/user-features.md)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name must not be blank.")
        return stripped


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=1, max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    confirm_new_password: str = Field(..., min_length=1, max_length=MAX_PASSWORD_LENGTH)

    @model_validator(mode="after")
    def validate_passwords(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match.")
        if self.new_password == self.current_password:
            raise ValueError("The new password must be different from the current password.")
        return self


class ChangePasswordResponse(BaseModel):
    message: str = "Password changed successfully."


ThemePreference = Literal["light", "dark"]


class NotificationSettings(BaseModel):
    #: In-app only: show a banner on the Alerts page when an alert has triggered. No email/push exists.
    price_alerts: bool = True


class SettingsResponse(BaseModel):
    #: null until the user explicitly chooses one — the device's own theme is then left alone.
    theme: Optional[ThemePreference] = None
    notifications: NotificationSettings = NotificationSettings()


class NotificationSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_alerts: Optional[bool] = None


class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Optional[ThemePreference] = None
    notifications: Optional[NotificationSettingsUpdate] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "SettingsUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Provide at least one setting to update.")
        if "notifications" in self.model_fields_set and self.notifications is None:
            raise ValueError("notifications cannot be null.")
        return self
