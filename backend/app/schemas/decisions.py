"""Pydantic response models for the Risk & Decision Engine (Phase 14).

A decision is MODEL-BASED decision support — never a guarantee and never an
order. `decision` is null (with an explanatory `status`) whenever the available
data cannot support an honest BUY/HOLD/SELL; numbers are only ever filled from
the deterministic engine, and `confidence` is null with
`confidence_status == "unavailable"` when it cannot be established.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

DecisionValue = Literal["BUY", "HOLD", "SELL"]
RiskLevelValue = Literal["VERY_LOW", "LOW", "MODERATE", "HIGH", "VERY_HIGH"]
DecisionStatus = Literal["VALID", "INSUFFICIENT_DATA", "STALE_DATA", "PREDICTION_UNAVAILABLE", "ANALYSIS_UNAVAILABLE"]
ModuleState = Literal["available", "missing", "stale", "insufficient_data", "unavailable"]

DISCLAIMER = (
    "This decision is generated from available market, technical, fundamental, sentiment, and "
    "machine-learning signals. It is not a guarantee of future performance."
)


class RiskSubFactorSchema(BaseModel):
    key: str
    label: str
    #: Raw input behind the sub-score (null for categorical inputs such as the trend label).
    value: Optional[float] = None
    #: 0-100, higher = riskier.
    score: float
    weight: float


class RiskComponentSchema(BaseModel):
    key: str
    label: str
    weight: float
    available: bool
    score: Optional[float] = None
    #: Points this component adds to the final risk score.
    contribution: Optional[float] = None
    reason: Optional[str] = None
    factors: list[RiskSubFactorSchema] = Field(default_factory=list)


class RiskSchema(BaseModel):
    available: bool
    #: 0-100 (null when it cannot be established from the available data).
    score: Optional[float] = None
    level: Optional[RiskLevelValue] = None
    #: Share (0-100) of the risk model backed by real data.
    coverage_percent: float
    components: list[RiskComponentSchema] = Field(default_factory=list)
    #: Risk-only factor sentences (strengths / risk factors derived from the risk components).
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    reason: Optional[str] = None
    config_version: str


class SignalsSchema(BaseModel):
    #: BULLISH | NEUTRAL | BEARISH | UNAVAILABLE
    technical: str
    #: STRONG | NEUTRAL | WEAK | UNAVAILABLE
    fundamental: str
    #: POSITIVE | NEUTRAL | NEGATIVE | UNAVAILABLE
    sentiment: str
    #: BULLISH | NEUTRAL | BEARISH | UNAVAILABLE
    prediction: str
    #: VERY_LOW | LOW | MODERATE | HIGH | VERY_HIGH | UNAVAILABLE
    risk: str


class SignalScoresSchema(BaseModel):
    """Per-module directional scores, -100 (bearish) .. +100 (bullish); null when the module was not used."""

    technical: Optional[float] = None
    fundamental: Optional[float] = None
    sentiment: Optional[float] = None
    prediction: Optional[float] = None


class OverrideSchema(BaseModel):
    rule: str
    description: str


class AgreementSchema(BaseModel):
    #: 0-1 share of module weight that points the same way (null when fewer than one module is usable).
    cross_module: Optional[float] = None
    intra_module: Optional[float] = None
    conflict_share: float = 0.0
    conflicting: bool = False
    bullish_modules: int = 0
    bearish_modules: int = 0
    neutral_modules: int = 0


class ModuleQualitySchema(BaseModel):
    available: bool
    state: ModuleState
    reason: Optional[str] = None
    as_of: Optional[datetime] = None


class DataQualitySummary(BaseModel):
    usable_modules: list[str] = Field(default_factory=list)
    module_coverage_percent: float = 0.0
    risk_coverage_percent: float = 0.0
    prediction_available: bool = False


class DataQualitySchema(BaseModel):
    market: ModuleQualitySchema
    technical: ModuleQualitySchema
    fundamental: ModuleQualitySchema
    sentiment: ModuleQualitySchema
    prediction: ModuleQualitySchema
    summary: DataQualitySummary


class DecisionResponse(BaseModel):
    coin_id: str
    symbol: Optional[str] = None
    kind: Literal["model_based_decision"] = "model_based_decision"
    decision: Optional[DecisionValue] = None
    status: DecisionStatus
    status_reason: Optional[str] = None
    #: Risk-adjusted combined score, -100..+100.
    decision_score: Optional[float] = None
    #: Combined score before the risk adjustment.
    raw_score: Optional[float] = None
    risk_adjustment: Optional[float] = None
    #: 0-100; null with confidence_status "unavailable" when it cannot be established.
    confidence: Optional[float] = None
    confidence_status: Literal["computed", "unavailable"]
    risk_score: Optional[float] = None
    risk_level: Optional[RiskLevelValue] = None
    risk: RiskSchema
    signals: SignalsSchema
    signal_scores: SignalScoresSchema
    #: Effective weight of each module that was used (sums to the weight actually applied).
    module_weights: dict[str, float] = Field(default_factory=dict)
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    #: Decision implied by the score alone, before the override rules.
    base_decision: Optional[DecisionValue] = None
    overrides: list[OverrideSchema] = Field(default_factory=list)
    agreement: AgreementSchema
    data_quality: DataQualitySchema
    warnings: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    generated_at: datetime
    expires_at: datetime
    #: True when expires_at has passed (only possible on /latest, which never recalculates).
    is_stale: bool = False
    engine_version: str
    risk_config_version: str
    disclaimer: str = DISCLAIMER


class RiskResponse(BaseModel):
    coin_id: str
    symbol: Optional[str] = None
    risk: RiskSchema
    risk_score: Optional[float] = None
    risk_level: Optional[RiskLevelValue] = None
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    data_quality: DataQualitySchema
    generated_at: datetime
    expires_at: datetime
    is_stale: bool = False
    engine_version: str
    risk_config_version: str
    disclaimer: str = DISCLAIMER
