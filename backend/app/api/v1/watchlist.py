"""Watchlist endpoints (Phase 16). Every route requires a valid JWT; the user comes from the token only."""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.watchlist import (
    WatchlistAddRequest,
    WatchlistAddResponse,
    WatchlistRemoveResponse,
    WatchlistResponse,
    WatchlistStatusResponse,
)
from app.services.user_feature_common import user_object_id
from app.services.watchlist_service import WatchlistService
from app.utils.pagination import DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


def _service() -> WatchlistService:
    return WatchlistService()


@router.get("", response_model=WatchlistResponse)
async def list_watchlist(
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> WatchlistResponse:
    """The authenticated user's watched coins, newest first, with CURRENT market data joined at read time."""
    return await _service().list_items(user_object_id(current_user), page, limit)


@router.post("", response_model=WatchlistAddResponse, status_code=201)
async def add_to_watchlist(
    payload: WatchlistAddRequest, current_user: dict[str, Any] = Depends(get_current_user)
) -> WatchlistAddResponse:
    """409 WATCHLIST_ALREADY_EXISTS if the coin is already watched; 404 COIN_NOT_FOUND for an unknown coin."""
    return await _service().add(user_object_id(current_user), payload.coin_id)


@router.get("/{coin_id}", response_model=WatchlistStatusResponse)
async def watchlist_status(coin_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> WatchlistStatusResponse:
    """Is this coin on MY watchlist?"""
    return await _service().status(user_object_id(current_user), coin_id)


@router.delete("/{coin_id}", response_model=WatchlistRemoveResponse)
async def remove_from_watchlist(
    coin_id: str, current_user: dict[str, Any] = Depends(get_current_user)
) -> WatchlistRemoveResponse:
    return await _service().remove(user_object_id(current_user), coin_id)
