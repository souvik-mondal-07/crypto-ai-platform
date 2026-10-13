"""Analysis-history endpoints (Phase 16). Every record belongs to the authenticated user, from the JWT only."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response

from app.core.dependencies import get_current_user
from app.schemas.history import HistoryCreateRequest, HistoryDeleteResponse, HistoryEntry, HistoryListResponse
from app.services.history_service import HistoryService
from app.services.user_feature_common import user_object_id
from app.utils.pagination import DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter(prefix="/history", tags=["History"])


def _service() -> HistoryService:
    return HistoryService()


@router.get("", response_model=HistoryListResponse)
async def list_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=MAX_LIMIT),
    coin_id: Optional[str] = Query(None, min_length=24, max_length=24),
    analysis_type: Optional[str] = Query(None, max_length=32),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> HistoryListResponse:
    """The user's history, newest first; optionally narrowed to one coin and/or analysis type."""
    return await _service().list_entries(user_object_id(current_user), page, limit, coin_id, analysis_type)


@router.post("", response_model=HistoryEntry, status_code=201)
async def record_history(
    payload: HistoryCreateRequest, response: Response, current_user: dict[str, Any] = Depends(get_current_user)
) -> HistoryEntry:
    """
    Record that the user viewed/generated an analysis. Status, decision and risk level are read from
    the stored analysis server-side. An identical entry from the last few minutes is returned (200)
    instead of writing a duplicate.
    """
    entry, created = await _service().record(user_object_id(current_user), payload)
    if not created:
        response.status_code = 200
    return entry


@router.get("/{entry_id}", response_model=HistoryEntry)
async def get_history_entry(entry_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> HistoryEntry:
    return await _service().get_entry(user_object_id(current_user), entry_id)


@router.delete("/{entry_id}", response_model=HistoryDeleteResponse)
async def delete_history_entry(entry_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> HistoryDeleteResponse:
    return await _service().delete_entry(user_object_id(current_user), entry_id)
