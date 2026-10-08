"""Risk & Decision endpoints (Phase 14). Logic lives in DecisionService; this layer only routes.

Like the other analysis endpoints these are not individually token-gated (the frontend routes
are behind ProtectedRoute). A decision is MODEL-BASED decision support, not advice or an order.
"""

from fastapi import APIRouter, Query

from app.schemas.decisions import DecisionResponse, RiskResponse
from app.services.decision_service import DecisionService

router = APIRouter(prefix="/decisions", tags=["Decisions"])


def _service() -> DecisionService:
    return DecisionService()


# Static path segments first so "latest" / "risk" can never be captured as a coin id.
@router.get("/{coin_id}/latest", response_model=DecisionResponse)
async def get_latest_decision(coin_id: str) -> DecisionResponse:
    """Most recent stored decision; never calculates one. `is_stale` flags an expired one."""
    return await _service().get_latest(coin_id)


@router.get("/{coin_id}/risk", response_model=RiskResponse)
async def get_coin_risk(coin_id: str) -> RiskResponse:
    """The risk half of the latest (or freshly calculated) decision: score, level, components, factors."""
    return await _service().get_risk(coin_id)


@router.get("/{coin_id}", response_model=DecisionResponse)
async def get_decision(
    coin_id: str,
    force_refresh: bool = Query(False, description="Recalculate now instead of using a fresh stored decision"),
) -> DecisionResponse:
    """
    BUY / HOLD / SELL with risk, confidence, signals and factors for a coin, by its internal ID.

    `decision` is null (with `status` explaining why) when the available data cannot support one.
    Nothing is trained and no LLM is involved: the result comes from deterministic rules.
    """
    return await _service().get_decision(coin_id, force_refresh=force_refresh)
