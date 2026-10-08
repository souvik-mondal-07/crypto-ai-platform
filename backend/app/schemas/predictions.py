"""Pydantic response models for ML predictions (Phase 13).

Everything here is a MODEL ESTIMATE (`kind == "model_prediction"`), never a market
fact, and carries the standard disclaimer. Numeric fields are only ever filled
from actual model output; `confidence` is null with `confidence_status ==
"unavailable"` whenever it cannot be calibrated defensibly.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PredictionHorizon = Literal["1h", "4h", "24h", "7d", "30d"]

DISCLAIMER = (
    "This is a machine-learning estimate based on historical data and available features. "
    "It is not a guarantee of future performance."
)


class ReturnRange(BaseModel):
    lower: float
    upper: float


class PriceRange(BaseModel):
    lower: float
    upper: float


class ModelEvaluation(BaseModel):
    """Held-out (test-set) evidence the model was activated on."""

    test_mae: Optional[float] = None
    baseline_mae: Optional[float] = None
    test_directional_accuracy: Optional[float] = None
    test_samples: Optional[int] = None
    interval_coverage_test: Optional[float] = None


class PredictionResponse(BaseModel):
    # `model` / `model_version` are legitimate field names, not pydantic namespace clashes.
    model_config = ConfigDict(protected_namespaces=())

    coin_id: str
    symbol: Optional[str] = None
    horizon: PredictionHorizon
    #: Always "model_prediction" — distinguishes this from observed market data.
    kind: Literal["model_prediction"] = "model_prediction"
    #: Close of the last COMPLETED candle the forecast starts from (market fact used as input).
    current_price: float
    reference_time: datetime
    target_time: datetime
    #: Fractional return, 0.024 == +2.4%.
    predicted_return: float
    predicted_return_range: Optional[ReturnRange] = None
    predicted_price_range: Optional[PriceRange] = None
    #: Nominal coverage of the range (0.8 = designed to contain ~80% of outcomes).
    range_nominal_coverage: Optional[float] = None
    direction: Literal["up", "down", "flat"]
    #: Calibrated probability that the predicted DIRECTION is right (not that a price is hit).
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence_status: Literal["calibrated", "unavailable"]
    confidence_note: Optional[str] = None
    model: str
    model_version: str
    feature_version: str
    evaluation: Optional[ModelEvaluation] = None
    trained_at: Optional[str] = None
    generated_at: datetime
    expires_at: datetime
    #: True when expires_at has passed (only possible on /latest, which never regenerates).
    is_stale: bool = False
    disclaimer: str = DISCLAIMER


class UnavailableHorizon(BaseModel):
    horizon: PredictionHorizon
    #: model_unavailable | insufficient_data
    status: Literal["model_unavailable", "insufficient_data"]
    reason: str


class PredictionListResponse(BaseModel):
    coin_id: str
    symbol: Optional[str] = None
    #: Only horizons with a valid prediction — the UI offers exactly these.
    predictions: list[PredictionResponse]
    unavailable: list[UnavailableHorizon] = Field(default_factory=list)
    generated_at: datetime
    disclaimer: str = DISCLAIMER
