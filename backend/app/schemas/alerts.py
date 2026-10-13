"""Pydantic models for /api/v1/alerts (Phase 16). Price alerts only; nothing here trades."""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AlertCondition = Literal["ABOVE", "BELOW"]
AlertStatus = Literal["ACTIVE", "TRIGGERED", "DISABLED", "EXPIRED"]
#: What a user may set by hand. TRIGGERED / EXPIRED are only ever set by the evaluation service.
UserSettableStatus = Literal["ACTIVE", "DISABLED"]

MAX_TARGET_PRICE = 1e12


def _future_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if aware <= datetime.now(timezone.utc):
        raise ValueError("expires_at must be in the future.")
    return aware


class AlertCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coin_id: str = Field(..., min_length=24, max_length=24)
    condition: AlertCondition
    target_price: float = Field(..., gt=0, le=MAX_TARGET_PRICE, allow_inf_nan=False)
    expires_at: Optional[datetime] = None

    _expires = field_validator("expires_at")(_future_utc)


class AlertUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: Optional[AlertCondition] = None
    target_price: Optional[float] = Field(None, gt=0, le=MAX_TARGET_PRICE, allow_inf_nan=False)
    status: Optional[UserSettableStatus] = None
    #: Send null to remove the expiry; omit to leave it unchanged.
    expires_at: Optional[datetime] = None

    _expires = field_validator("expires_at")(_future_utc)

    @model_validator(mode="after")
    def validate_fields(self) -> "AlertUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        for name in ("condition", "target_price", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        return self


class AlertResponse(BaseModel):
    id: str
    coin_id: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    logo_url: Optional[str] = None
    alert_type: Literal["price"] = "price"
    condition: AlertCondition
    target_price: float
    status: AlertStatus
    #: The coin's current synced price, for context only — null if none is available.
    current_price: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    triggered_at: Optional[datetime] = None
    triggered_price: Optional[float] = None
    expires_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    limit: int
    pages: int


class AlertDeleteResponse(BaseModel):
    id: str
    deleted: bool = True


class AlertCheckResponse(BaseModel):
    """Outcome of ONE real evaluation pass against the stored market data."""

    checked: int
    triggered: int
    expired: int
    skipped_no_price: int
    skipped_stale: int
    triggered_alert_ids: list[str]
    checked_at: datetime
