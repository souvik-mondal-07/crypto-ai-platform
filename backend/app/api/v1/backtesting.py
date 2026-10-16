"""Backtesting & model accuracy (Phase 17). Historical evaluation and simulation only — no trading.

Everything requires authentication. Accuracy endpoints describe the platform's own stored predictions/decisions
(public market data, not user data); backtest RUNS belong to the authenticated user, taken from the JWT only.
"""

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from app.config.backtest_config import (
    MAX_BACKTEST_DAYS,
    MAX_BARS_PER_COIN,
    MAX_CAPITAL,
    MAX_CONCURRENT_RUNS_PER_USER,
    MAX_COINS_PER_BACKTEST,
    MAX_STORED_TRADES,
    MIN_BACKTEST_DAYS,
)
from app.core.dependencies import get_current_user
from app.schemas.backtesting import (
    AccuracyResponse,
    BacktestConfigResponse,
    BacktestRunCreate,
    BacktestRunDetail,
    BacktestRunList,
    BacktestRunSummary,
    BacktestTradesPage,
    DecisionEvaluationResponse,
    RefreshState,
)
from app.services.backtest_service import DISCLAIMER, BacktestService
from app.services.evaluation_service import EvaluationService
from app.services.user_feature_common import user_object_id
from app.utils.pagination import MAX_LIMIT

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from ml.evaluation.constants import (  # noqa: E402
    BACKTEST_ENGINE_VERSION,
    DECISION_HORIZONS,
    INTERVAL_SECONDS,
    METHODOLOGY_VERSION,
    MIN_SAMPLE_SIZE,
    STRATEGY_PHASE14,
    SUPPORTED_HORIZONS,
)
from ml.evaluation.backtest import SIZING_MODES  # noqa: E402

router = APIRouter(prefix="/backtesting", tags=["Backtesting"], dependencies=[Depends(get_current_user)])


def _evaluation() -> EvaluationService:
    return EvaluationService()


def _backtests() -> BacktestService:
    return BacktestService()


@router.get("/config", response_model=BacktestConfigResponse)
async def get_config() -> BacktestConfigResponse:
    """Engine/methodology versions, supported options, defaults and limits (so the UI hard-codes none of them)."""
    return BacktestConfigResponse(
        engine_version=BACKTEST_ENGINE_VERSION, methodology_version=METHODOLOGY_VERSION, strategy=STRATEGY_PHASE14,
        strategy_description="Long-only replay of the stored Phase 14 BUY/HOLD/SELL decisions: BUY opens a position, SELL closes it, HOLD does nothing; orders fill at the next bar's open.",
        horizons=list(SUPPORTED_HORIZONS), decision_horizons=list(DECISION_HORIZONS), min_sample_size=MIN_SAMPLE_SIZE,
        bar_intervals=list(INTERVAL_SECONDS), sizing_modes=list(SIZING_MODES),
        defaults={"starting_capital": 10000.0, "bar_interval": "1h", "sizing_mode": "fixed_fraction", "position_size": 0.25,
                  "max_allocation_pct": 0.5, "fee_rate": 0.001, "slippage_rate": 0.0005, "close_open_positions_at_end": True,
                  "benchmark": "equal_weight_buy_and_hold"},
        limits={"max_coins": MAX_COINS_PER_BACKTEST, "max_days": MAX_BACKTEST_DAYS, "min_days": MIN_BACKTEST_DAYS,
                "max_capital": MAX_CAPITAL, "max_bars_per_coin": MAX_BARS_PER_COIN,
                "max_concurrent_runs": MAX_CONCURRENT_RUNS_PER_USER, "max_stored_trades": MAX_STORED_TRADES},
        disclaimer=DISCLAIMER,
    )


@router.get("/accuracy", response_model=AccuracyResponse)
async def get_accuracy(
    horizon: Optional[str] = Query(None, max_length=8),
    model: Optional[str] = Query(None, max_length=64),
    model_version: Optional[str] = Query(None, max_length=64),
    coin_id: Optional[str] = Query(None, min_length=24, max_length=24),
) -> dict[str, Any]:
    """Prediction accuracy over MATCHED, matured predictions only. Reads stored results; never downloads data."""
    return await _evaluation().accuracy(coin_id=coin_id, horizon=horizon, model=model, model_version=model_version)


@router.post("/accuracy/refresh", response_model=RefreshState, status_code=202)
async def refresh_accuracy() -> dict[str, Any]:
    """Start matching matured predictions/decisions with real market outcomes in the background."""
    return await _evaluation().start_refresh()


@router.get("/accuracy/refresh", response_model=RefreshState)
async def refresh_status() -> dict[str, Any]:
    state = EvaluationService.refresh_state()
    return {**state, "accepted": False}


@router.get("/accuracy/{coin_id}", response_model=AccuracyResponse)
async def get_coin_accuracy(
    coin_id: str,
    horizon: Optional[str] = Query(None, max_length=8),
    model: Optional[str] = Query(None, max_length=64),
    model_version: Optional[str] = Query(None, max_length=64),
) -> dict[str, Any]:
    return await _evaluation().accuracy(coin_id=coin_id, horizon=horizon, model=model, model_version=model_version)


@router.get("/decisions", response_model=DecisionEvaluationResponse)
async def get_decision_evaluation(
    horizon: Optional[str] = Query(None, max_length=8),
    coin_id: Optional[str] = Query(None, min_length=24, max_length=24),
) -> dict[str, Any]:
    """BUY/HOLD/SELL evaluated against the return that followed (rules documented in docs/backtesting.md)."""
    return await _evaluation().decisions(coin_id=coin_id, horizon=horizon)


@router.post("/runs", response_model=BacktestRunSummary, status_code=202)
async def create_run(payload: BacktestRunCreate, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Queue a backtest for the authenticated user. Returns immediately; poll GET /runs/{run_id}."""
    return await _backtests().create_run(user_object_id(current_user), payload)


@router.get("/runs", response_model=BacktestRunList)
async def list_runs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=MAX_LIMIT),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return await _backtests().list_runs(user_object_id(current_user), page, limit)


@router.get("/runs/{run_id}", response_model=BacktestRunDetail)
async def get_run(run_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return await _backtests().get_run(user_object_id(current_user), run_id)


@router.get("/runs/{run_id}/trades", response_model=BacktestTradesPage)
async def get_run_trades(
    run_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=MAX_LIMIT),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return await _backtests().list_trades(user_object_id(current_user), run_id, page, limit)
