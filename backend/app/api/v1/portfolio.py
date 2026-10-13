"""Portfolio endpoints (Phase 16). Record-keeping only — no trading. User comes from the JWT only."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.portfolio import (
    HoldingCreateRequest,
    HoldingRemoveResponse,
    HoldingResponse,
    HoldingUpdateRequest,
    PortfolioResponse,
    TransactionListResponse,
)
from app.services.portfolio_service import PortfolioService
from app.services.user_feature_common import user_object_id
from app.utils.pagination import DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


def _service() -> PortfolioService:
    return PortfolioService()


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(current_user: dict[str, Any] = Depends(get_current_user)) -> PortfolioResponse:
    """Holdings valued at the CURRENT synced market price, with totals, P&L and allocation."""
    return await _service().get_portfolio(user_object_id(current_user))


@router.post("", response_model=HoldingResponse, status_code=201)
async def add_holding(payload: HoldingCreateRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> HoldingResponse:
    """Record a purchase (merged into an existing holding's weighted-average price). Executes no trade."""
    return await _service().add_holding(user_object_id(current_user), payload)


# Static segment before the dynamic one so "transactions" is never captured as a coin id.
@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    coin_id: Optional[str] = Query(None, min_length=24, max_length=24),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> TransactionListResponse:
    """The user's recorded purchases/adjustments, newest first."""
    return await _service().list_transactions(user_object_id(current_user), page, limit, coin_id)


@router.put("/{coin_id}", response_model=HoldingResponse)
async def update_holding(
    coin_id: str, payload: HoldingUpdateRequest, current_user: dict[str, Any] = Depends(get_current_user)
) -> HoldingResponse:
    return await _service().update_holding(user_object_id(current_user), coin_id, payload)


@router.delete("/{coin_id}", response_model=HoldingRemoveResponse)
async def remove_holding(coin_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> HoldingRemoveResponse:
    return await _service().remove_holding(user_object_id(current_user), coin_id)
