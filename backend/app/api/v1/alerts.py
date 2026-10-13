"""Price-alert endpoints (Phase 16). Every alert belongs to the authenticated user, from the JWT only."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.alerts import (
    AlertCheckResponse,
    AlertCreateRequest,
    AlertDeleteResponse,
    AlertListResponse,
    AlertResponse,
    AlertUpdateRequest,
)
from app.services.alert_service import AlertEvaluationService, AlertService
from app.services.user_feature_common import user_object_id
from app.utils.pagination import DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _service() -> AlertService:
    return AlertService()


def _evaluator() -> AlertEvaluationService:
    return AlertEvaluationService()


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    status: Optional[str] = Query(None, max_length=16),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> AlertListResponse:
    return await _service().list_alerts(user_object_id(current_user), page, limit, status)


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(payload: AlertCreateRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> AlertResponse:
    return await _service().create(user_object_id(current_user), payload)


@router.post("/check", response_model=AlertCheckResponse)
async def check_my_alerts(current_user: dict[str, Any] = Depends(get_current_user)) -> AlertCheckResponse:
    """
    Run ONE real evaluation of the caller's ACTIVE alerts against the stored market data. Alerts whose
    coin has no price, or whose price snapshot is stale, are skipped and counted — never triggered.
    """
    result = await _evaluator().evaluate(user_id=user_object_id(current_user))
    return result.to_response()


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str, payload: AlertUpdateRequest, current_user: dict[str, Any] = Depends(get_current_user)
) -> AlertResponse:
    return await _service().update(user_object_id(current_user), alert_id, payload)


@router.delete("/{alert_id}", response_model=AlertDeleteResponse)
async def delete_alert(alert_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> AlertDeleteResponse:
    return await _service().delete(user_object_id(current_user), alert_id)
