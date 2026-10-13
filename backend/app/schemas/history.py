"""Pydantic models for /api/v1/history (Phase 16)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AnalysisType = Literal["coin_analysis", "prediction", "risk_decision", "ai_analysis"]
HistoryStatus = Literal["COMPLETED", "UNAVAILABLE"]
ANALYSIS_TYPES: tuple[str, ...] = ("coin_analysis", "prediction", "risk_decision", "ai_analysis")


class HistoryCreateRequest(BaseModel):
    """The user + the outcome (status/decision/risk) are decided server-side; the client only says what was viewed."""

    model_config = ConfigDict(extra="forbid")

    coin_id: str = Field(..., min_length=24, max_length=24)
    analysis_type: AnalysisType


class HistoryEntry(BaseModel):
    id: str
    coin_id: str
    coin_name: Optional[str] = None
    symbol: Optional[str] = None
    analysis_type: AnalysisType
    status: HistoryStatus
    decision: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    summary: Optional[str] = None
    created_at: datetime


class HistoryListResponse(BaseModel):
    items: list[HistoryEntry]
    total: int
    page: int
    limit: int
    pages: int


class HistoryDeleteResponse(BaseModel):
    id: str
    deleted: bool = True
