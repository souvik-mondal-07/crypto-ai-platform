"""Feature-set definition and the leakage-safety flags for each feature group.

``FEATURE_VERSION`` is stored in every model artifact and every stored
prediction. Bump it whenever a feature's definition changes, so an old model is
never fed features computed a different way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FEATURE_VERSION = "v1"


@dataclass(frozen=True)
class FeatureConfig:
    #: Look-back windows, in candles of the horizon's interval.
    return_windows: tuple[int, ...] = (1, 3, 6, 12, 24)
    volatility_windows: tuple[int, ...] = (12, 24, 72)
    volume_windows: tuple[int, ...] = (12, 24)
    rsi_period: int = 14
    macd: tuple[int, int, int] = (12, 26, 9)
    sma_periods: tuple[int, ...] = (20, 50, 200)
    ema_periods: tuple[int, ...] = (20, 50)
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    atr_period: int = 14
    #: Causal support/resistance proxy (rolling extremes) window.
    sr_window: int = 48

    # --- sentiment (point-in-time, from stored articles) ---
    sentiment_window_hours: int = 24
    sentiment_min_articles: int = 3

    #: Fundamental *snapshot* fields come from the current market_data document.
    #: There is no stored history for them, so using them as training features
    #: would leak present-day information into the past. They stay OFF unless
    #: point-in-time history exists. (See ml/features/fundamental_features.py.)
    include_fundamental_snapshot: bool = False
    include_sentiment: bool = True


# Which feature groups are point-in-time safe (documented + asserted by tests).
POINT_IN_TIME_SAFE_GROUPS = {
    "market": True,
    "technical": True,
    "sentiment": True,       # computed from article publish times <= candle close
    "fundamental": False,    # current snapshot only
}
