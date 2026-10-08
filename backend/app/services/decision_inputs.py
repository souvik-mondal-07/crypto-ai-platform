"""Engine inputs (Phase 14).

The risk and decision engines never see Pydantic responses or database
documents. They see the small dataclasses below, each carrying a
`ModuleStatus` that says whether the data is real and usable:

    available | missing | stale | insufficient_data | unavailable

so "no data" can never be mistaken for "0", "neutral", "low risk" or "high
confidence". The `*_from_*` builders translate the EXISTING module outputs
(market snapshot, technical analysis, fundamentals, sentiment, prediction)
into these inputs by attribute access only, so they work with the real response
models and with plain stand-ins in tests.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.config.risk_config import (
    STATE_AVAILABLE,
    STATE_INSUFFICIENT,
    STATE_MISSING,
    STATE_STALE,
    STATE_UNAVAILABLE,
    DecisionConfig,
)
from app.services.scoring import is_number


@dataclass
class ModuleStatus:
    state: str = STATE_MISSING
    reason: Optional[str] = None
    as_of: Optional[datetime] = None

    @property
    def usable(self) -> bool:
        return self.state == STATE_AVAILABLE


def _status(state: str, reason: Optional[str] = None, as_of: Optional[datetime] = None) -> ModuleStatus:
    return ModuleStatus(state=state, reason=reason, as_of=as_of)


def _num(value: Any) -> Optional[float]:
    return float(value) if is_number(value) else None


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Input containers
# ---------------------------------------------------------------------------


@dataclass
class MarketInput:
    status: ModuleStatus = field(default_factory=ModuleStatus)
    price_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    high_24h_usd: Optional[float] = None
    low_24h_usd: Optional[float] = None
    percent_change_24h: Optional[float] = None
    percent_change_7d: Optional[float] = None
    percent_change_30d: Optional[float] = None
    percent_change_1y: Optional[float] = None


@dataclass
class TechnicalInput:
    status: ModuleStatus = field(default_factory=ModuleStatus)
    timeframe: Optional[str] = None
    trend: Optional[str] = None  # bullish | bearish | neutral
    rsi: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_crossover: Optional[str] = None  # bullish_crossover | bearish_crossover | none
    sma: dict[str, Optional[float]] = field(default_factory=dict)
    ema: dict[str, Optional[float]] = field(default_factory=dict)
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    atr: Optional[float] = None
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)
    volume_trend: Optional[str] = None


@dataclass
class FundamentalInput:
    status: ModuleStatus = field(default_factory=ModuleStatus)
    #: The existing Phase 11 rule-based score (0-100); None unless status == "scored".
    score: Optional[float] = None
    coverage_percent: Optional[float] = None
    market_cap_rank: Optional[int] = None
    market_cap_to_fdv: Optional[float] = None
    circulating_to_max_supply_percent: Optional[float] = None
    supply_type: Optional[str] = None
    distance_from_ath_percent: Optional[float] = None


@dataclass
class SentimentInput:
    status: ModuleStatus = field(default_factory=ModuleStatus)
    timeframe: Optional[str] = None
    label: Optional[str] = None
    average_score: Optional[float] = None  # -1..1
    positive_percent: Optional[float] = None
    negative_percent: Optional[float] = None
    total_articles: int = 0
    trend_direction: Optional[str] = None  # improving | declining | stable | insufficient_data


@dataclass
class PredictionInput:
    status: ModuleStatus = field(default_factory=ModuleStatus)
    horizon: Optional[str] = None
    model: Optional[str] = None
    direction: Optional[str] = None  # up | down | flat
    predicted_return: Optional[float] = None  # fraction
    return_lower: Optional[float] = None
    return_upper: Optional[float] = None
    confidence: Optional[float] = None  # 0-1 calibrated probability
    confidence_status: Optional[str] = None  # calibrated | unavailable


@dataclass
class DecisionInputs:
    market: MarketInput = field(default_factory=MarketInput)
    technical: TechnicalInput = field(default_factory=TechnicalInput)
    fundamental: FundamentalInput = field(default_factory=FundamentalInput)
    sentiment: SentimentInput = field(default_factory=SentimentInput)
    prediction: PredictionInput = field(default_factory=PredictionInput)

    def statuses(self) -> dict[str, ModuleStatus]:
        return {
            "market": self.market.status,
            "technical": self.technical.status,
            "fundamental": self.fundamental.status,
            "sentiment": self.sentiment.status,
            "prediction": self.prediction.status,
        }


# ---------------------------------------------------------------------------
# Builders from the existing module outputs
# ---------------------------------------------------------------------------


def market_from_snapshot(market: Any) -> MarketInput:
    """`market` is the MarketData schema (or None when no snapshot was synchronized)."""
    if market is None:
        return MarketInput(status=_status(STATE_MISSING, "No market data has been synchronized for this coin yet."))
    last = _aware(getattr(market, "last_updated", None))
    price = _num(getattr(market, "price_usd", None))
    if price is None or price <= 0:
        return MarketInput(status=_status(STATE_INSUFFICIENT, "The market snapshot has no usable price.", last))
    state, reason = STATE_AVAILABLE, None
    if getattr(market, "is_stale", False):
        state, reason = STATE_STALE, "The market data snapshot is out of date."
    return MarketInput(
        status=_status(state, reason, last),
        price_usd=price,
        market_cap_usd=_num(getattr(market, "market_cap_usd", None)),
        volume_24h_usd=_num(getattr(market, "volume_24h_usd", None)),
        high_24h_usd=_num(getattr(market, "high_24h_usd", None)),
        low_24h_usd=_num(getattr(market, "low_24h_usd", None)),
        percent_change_24h=_num(getattr(market, "percent_change_24h", None)),
        percent_change_7d=_num(getattr(market, "percent_change_7d", None)),
        percent_change_30d=_num(getattr(market, "percent_change_30d", None)),
        percent_change_1y=_num(getattr(market, "percent_change_1y", None)),
    )


def technical_from_response(resp: Any, now: datetime, cfg: DecisionConfig) -> TechnicalInput:
    """`resp` is a TechnicalAnalysisResponse."""
    calculated_at = _aware(getattr(resp, "calculated_at", None))
    state, reason = STATE_AVAILABLE, None
    if calculated_at is not None and (now - calculated_at).total_seconds() > cfg.technical_max_age_seconds:
        state, reason = STATE_STALE, "The technical analysis snapshot is out of date."
    return TechnicalInput(
        status=_status(state, reason, calculated_at),
        timeframe=getattr(resp, "timeframe", None),
        trend=getattr(getattr(resp, "trend", None), "trend", None),
        rsi=_num(getattr(resp.rsi, "current", None)),
        macd_histogram=_num(getattr(resp.macd.current, "histogram", None)),
        macd_crossover=getattr(resp.macd, "crossover", None),
        sma={k: _num(v) for k, v in (resp.moving_averages.sma or {}).items()},
        ema={k: _num(v) for k, v in (resp.moving_averages.ema or {}).items()},
        bollinger_upper=_num(resp.bollinger_bands.upper),
        bollinger_middle=_num(resp.bollinger_bands.middle),
        bollinger_lower=_num(resp.bollinger_bands.lower),
        atr=_num(resp.atr.current),
        support_levels=[float(v) for v in (resp.support_resistance.support_levels or []) if is_number(v)],
        resistance_levels=[float(v) for v in (resp.support_resistance.resistance_levels or []) if is_number(v)],
        volume_trend=getattr(resp.volume, "trend", None),
    )


def fundamental_from_response(resp: Any) -> FundamentalInput:
    """`resp` is a FundamentalAnalysisResponse."""
    score = resp.score
    scored = getattr(score, "status", None) == "scored" and is_number(getattr(score, "score", None))
    metrics = resp.calculated_metrics
    market = getattr(resp, "market", None)
    supply = getattr(resp, "supply", None)
    freshness = getattr(resp, "freshness", None)

    def metric(name: str) -> Optional[float]:
        m = getattr(metrics, name, None)
        return _num(getattr(m, "value", None))

    fi = FundamentalInput(
        score=float(score.score) if scored else None,
        coverage_percent=_num(getattr(score, "coverage_percent", None)),
        market_cap_rank=getattr(market, "market_cap_rank", None) if market is not None else None,
        market_cap_to_fdv=metric("market_cap_to_fdv"),
        circulating_to_max_supply_percent=metric("circulating_to_max_supply_percent"),
        supply_type=getattr(supply, "supply_type", None) if supply is not None else None,
        distance_from_ath_percent=metric("distance_from_ath_percent"),
    )
    has_anything = (
        fi.score is not None or fi.market_cap_rank is not None or fi.market_cap_to_fdv is not None
        or fi.distance_from_ath_percent is not None
    )
    updated = _aware(getattr(getattr(resp, "timestamps", None), "calculated_at", None))
    if not has_anything:
        fi.status = _status(STATE_INSUFFICIENT, "Not enough fundamental data is available for this coin.", updated)
    elif freshness is not None and getattr(freshness, "market_data_is_stale", False):
        fi.status = _status(STATE_STALE, "The market data behind the fundamental analysis is out of date.", updated)
    else:
        fi.status = _status(STATE_AVAILABLE, None, updated)
    return fi


def sentiment_from_response(resp: Any) -> SentimentInput:
    """`resp` is a CoinSentimentResponse."""
    calculated = _aware(getattr(resp, "calculated_at", None))
    trend = getattr(resp, "trend", None)
    si = SentimentInput(
        timeframe=getattr(resp, "timeframe", None),
        label=getattr(resp, "sentiment_label", None),
        average_score=_num(getattr(resp, "average_score", None)),
        positive_percent=_num(getattr(resp, "positive_percent", None)),
        negative_percent=_num(getattr(resp, "negative_percent", None)),
        total_articles=int(getattr(resp, "total_articles", 0) or 0),
        trend_direction=getattr(trend, "direction", None) if trend is not None else None,
    )
    if getattr(resp, "status", None) != "ok" or si.average_score is None:
        model_status = getattr(resp, "model_status", None)
        if si.total_articles == 0 and model_status in ("disabled", "unavailable"):
            si.status = _status(STATE_UNAVAILABLE, "The sentiment model is not available, so news has not been analysed.", calculated)
        else:
            needed = getattr(resp, "min_articles_required", None)
            extra = f" ({si.total_articles} analysed, {needed} needed)" if needed is not None else ""
            si.status = _status(STATE_INSUFFICIENT, f"Too few analysed news articles to describe sentiment{extra}.", calculated)
    else:
        si.status = _status(STATE_AVAILABLE, None, calculated)
    return si


def prediction_from_response(resp: Any, now: datetime, cfg: DecisionConfig) -> PredictionInput:
    """`resp` is a PredictionResponse (Phase 13)."""
    generated = _aware(getattr(resp, "generated_at", None))
    rr = getattr(resp, "predicted_return_range", None)
    pi = PredictionInput(
        horizon=getattr(resp, "horizon", None),
        model=getattr(resp, "model", None),
        direction=getattr(resp, "direction", None),
        predicted_return=_num(getattr(resp, "predicted_return", None)),
        return_lower=_num(getattr(rr, "lower", None)) if rr is not None else None,
        return_upper=_num(getattr(rr, "upper", None)) if rr is not None else None,
        confidence=_num(getattr(resp, "confidence", None)),
        confidence_status=getattr(resp, "confidence_status", None),
    )
    if pi.direction is None or pi.predicted_return is None:
        pi.status = _status(STATE_INSUFFICIENT, "The stored prediction has no usable direction or return.", generated)
    elif generated is not None and (now - generated).total_seconds() > cfg.prediction_max_age_seconds:
        pi.status = _status(STATE_STALE, "The latest model prediction is too old to use.", generated)
    else:
        pi.status = _status(STATE_AVAILABLE, None, generated)
    return pi


def unavailable_input(kind: str, state: str, reason: str) -> Any:
    """An input of the given kind carrying only a (non-available) status and reason."""
    status = _status(state, reason)
    factory = {
        "market": MarketInput,
        "technical": TechnicalInput,
        "fundamental": FundamentalInput,
        "sentiment": SentimentInput,
        "prediction": PredictionInput,
    }[kind]
    return factory(status=status)
