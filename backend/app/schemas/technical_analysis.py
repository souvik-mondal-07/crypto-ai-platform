"""
Pydantic response models for technical-analysis endpoints (Phase 10).

Mirrors the storage shape documented in docs/database-schema.md for
the `technical_analysis` collection — every field there has a
corresponding schema field here.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RsiData(BaseModel):
    period: int
    current: Optional[float] = None
    zone: Optional[str] = None  # "overbought" | "oversold" | "neutral"
    history: list[Optional[float]] = []


class MacdPointSchema(BaseModel):
    timestamp: str
    macd: Optional[float] = None
    signal: Optional[float] = None
    histogram: Optional[float] = None


class MacdData(BaseModel):
    fast_period: int
    slow_period: int
    signal_period: int
    current: MacdPointSchema
    crossover: str  # "bullish_crossover" | "bearish_crossover" | "none"
    history: list[MacdPointSchema] = []


class MovingAverages(BaseModel):
    """Keyed by period, e.g. sma={"20": ..., "50": ..., "200": ...}."""

    sma: dict[str, Optional[float]]
    ema: dict[str, Optional[float]]


class BollingerBandsData(BaseModel):
    period: int
    num_std_dev: float
    upper: Optional[float] = None
    middle: Optional[float] = None
    lower: Optional[float] = None


class AtrData(BaseModel):
    period: int
    current: Optional[float] = None
    history: list[Optional[float]] = []


class HistoricalVolumePoint(BaseModel):
    timestamp: datetime
    volume: float


class VolumeAnalysis(BaseModel):
    current_volume_24h_usd: Optional[float] = None
    historical_volume: list[HistoricalVolumePoint] = []
    average_volume: Optional[float] = None
    volume_change_percent: Optional[float] = None
    trend: str = "unavailable"  # increasing | decreasing | neutral | unavailable
    historical_volume_source: Optional[str] = None


class SupportResistanceData(BaseModel):
    support_levels: list[float] = []
    resistance_levels: list[float] = []


class TrendAnalysis(BaseModel):
    """
    Descriptive technical-trend label only ("bullish" | "bearish" |
    "neutral") — never a BUY/HOLD/SELL decision. See
    app/services/indicators.py::classify_trend for the documented
    rule set behind this classification.
    """

    trend: str
    signals_considered: int


class TechnicalAnalysisResponse(BaseModel):
    coin_id: str
    symbol: str
    timeframe: str
    calculated_at: datetime
    candle_count: int
    rsi: RsiData
    macd: MacdData
    moving_averages: MovingAverages
    bollinger_bands: BollingerBandsData
    atr: AtrData
    volume: VolumeAnalysis
    support_resistance: SupportResistanceData
    trend: TrendAnalysis
    data_source: str
