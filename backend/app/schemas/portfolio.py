"""Pydantic models for /api/v1/portfolio (Phase 16). Record-keeping only — no trading."""

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Generous but finite bounds: they reject absurd/overflowing input without limiting real use.
MAX_QUANTITY = 1e15
MAX_PRICE = 1e12
MAX_NOTES_LENGTH = 500


def _check_not_future(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if aware > datetime.now(timezone.utc) + timedelta(days=1):
        raise ValueError("Transaction date cannot be in the future.")
    return aware


def _clean_notes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class HoldingCreateRequest(BaseModel):
    """Record a purchase. If the coin is already held the purchase is merged (weighted-average price)."""

    model_config = ConfigDict(extra="forbid")

    coin_id: str = Field(..., min_length=24, max_length=24)
    quantity: float = Field(..., gt=0, le=MAX_QUANTITY, allow_inf_nan=False)
    price: float = Field(..., ge=0, le=MAX_PRICE, allow_inf_nan=False, description="Buy price per unit, USD")
    fee: Optional[float] = Field(None, ge=0, le=MAX_PRICE, allow_inf_nan=False)
    bought_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=MAX_NOTES_LENGTH)

    _bought_at = field_validator("bought_at")(_check_not_future)
    _notes = field_validator("notes")(_clean_notes)


class HoldingUpdateRequest(BaseModel):
    """Correct a recorded holding directly. At least one field is required."""

    model_config = ConfigDict(extra="forbid")

    quantity: Optional[float] = Field(None, gt=0, le=MAX_QUANTITY, allow_inf_nan=False)
    average_buy_price: Optional[float] = Field(None, ge=0, le=MAX_PRICE, allow_inf_nan=False)
    notes: Optional[str] = Field(None, max_length=MAX_NOTES_LENGTH)

    _notes = field_validator("notes")(_clean_notes)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "HoldingUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        if "quantity" in self.model_fields_set and self.quantity is None:
            raise ValueError("quantity cannot be null.")
        if "average_buy_price" in self.model_fields_set and self.average_buy_price is None:
            raise ValueError("average_buy_price cannot be null.")
        return self


class HoldingResponse(BaseModel):
    coin_id: str
    name: str
    symbol: str
    logo_url: Optional[str] = None
    quantity: float
    average_buy_price: float
    invested_value: float
    #: False when no market price has been synced for this coin — current_value / P&L are then null, never guessed.
    has_price: bool
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    percent_change_24h: Optional[float] = None
    allocation_pct: Optional[float] = None
    price_last_updated: Optional[datetime] = None
    price_is_stale: bool = False
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PortfolioSummary(BaseModel):
    #: Sum of current value over holdings that HAVE a market price.
    total_current_value: float
    #: Sum of invested value over ALL holdings.
    total_invested: float
    #: Invested value of the priced holdings only — the base the P&L below is measured against.
    priced_invested: float
    total_unrealized_pnl: Optional[float] = None
    total_unrealized_pnl_pct: Optional[float] = None
    holdings_count: int
    unpriced_count: int
    #: True when some holdings had no price, so the totals cover only part of the portfolio.
    is_partial: bool


class PortfolioResponse(BaseModel):
    summary: PortfolioSummary
    holdings: list[HoldingResponse]
    currency: Literal["USD"] = "USD"


TransactionType = Literal["buy", "adjustment"]


class TransactionResponse(BaseModel):
    id: str
    coin_id: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    transaction_type: TransactionType
    quantity: float
    price: float
    fee: Optional[float] = None
    notes: Optional[str] = None
    transaction_at: datetime
    created_at: datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    limit: int
    pages: int


class HoldingRemoveResponse(BaseModel):
    coin_id: str
    removed: bool = True
