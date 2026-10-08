"""Technical features — built on the Phase 10 indicator functions.

RSI, MACD, SMA, EMA, Bollinger Bands, ATR and the trend classifier come from
``backend/app/services/indicators.py`` (loaded via ``_indicators_bridge``), so the
ML features and the Technical Analysis section of the UI use the same math.

Leakage note: all of those indicators are causal (value at ``t`` depends on
candles ``<= t``). The Phase 10 ``support_resistance`` function is NOT used for
training: it confirms a pivot with ``window`` candles *after* it, which at row ``t``
would be using future candles. Support/resistance is therefore represented by
causal rolling extremes (distance to the lowest low / highest high of the last
``sr_window`` candles).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml.config.feature_config import FeatureConfig
from ml.features._indicators_bridge import load_indicators

_TREND_CODE = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}


def _arr(values: list[Optional[float]]) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in values], dtype="float64")


def build_technical_features(candles: pd.DataFrame, cfg: FeatureConfig = FeatureConfig()) -> pd.DataFrame:
    ind = load_indicators()
    n = len(candles)
    idx = candles.index
    close = candles["close"].astype("float64")
    high = candles["high"].astype("float64")
    low = candles["low"].astype("float64")
    volume = candles["volume"].astype("float64")
    closes = close.tolist()

    candle_objs = [
        ind.Candle(timestamp=str(ts), open=o, high=h, low=l, close=c, volume=v)
        for ts, o, h, l, c, v in zip(
            candles["timestamp"], candles["open"], high, low, close, volume
        )
    ]

    feats: dict[str, np.ndarray | pd.Series] = {}

    rsi = _arr(ind.rsi(closes, cfg.rsi_period))
    feats["rsi"] = rsi

    fast, slow, signal = cfg.macd
    macd_pts = ind.macd(closes, fast, slow, signal)
    macd_line = _arr([p.macd for p in macd_pts])
    macd_sig = _arr([p.signal for p in macd_pts])
    macd_hist = _arr([p.histogram for p in macd_pts])
    # MACD is in price units -> divide by close to make it scale-free.
    feats["macd"] = macd_line / close.to_numpy()
    feats["macd_signal"] = macd_sig / close.to_numpy()
    feats["macd_hist"] = macd_hist / close.to_numpy()

    sma_last: dict[int, np.ndarray] = {}
    for p in cfg.sma_periods:
        s = _arr(ind.sma(closes, p))
        sma_last[p] = s
        feats[f"close_vs_sma_{p}"] = close.to_numpy() / s - 1.0
    for p in cfg.ema_periods:
        e = _arr(ind.ema(closes, p))
        feats[f"close_vs_ema_{p}"] = close.to_numpy() / e - 1.0
    if 20 in sma_last and 50 in sma_last:
        feats["sma_20_vs_50"] = sma_last[20] / sma_last[50] - 1.0
    if 50 in sma_last and 200 in sma_last:
        feats["sma_50_vs_200"] = sma_last[50] / sma_last[200] - 1.0

    bb = ind.bollinger_bands(closes, cfg.bollinger_period, cfg.bollinger_std)
    bb_up = _arr([b.upper for b in bb])
    bb_mid = _arr([b.middle for b in bb])
    bb_low = _arr([b.lower for b in bb])
    c = close.to_numpy()
    feats["bb_upper_dist"] = bb_up / c - 1.0
    feats["bb_lower_dist"] = c / bb_low - 1.0
    feats["bb_width"] = (bb_up - bb_low) / bb_mid
    with np.errstate(divide="ignore", invalid="ignore"):
        feats["bb_position"] = (c - bb_low) / (bb_up - bb_low)

    atr = _arr(ind.atr(candle_objs, cfg.atr_period))
    feats["atr_pct"] = atr / c

    # Volume indicators ---------------------------------------------------------
    vol_sma = volume.rolling(20, min_periods=20).mean()
    feats["volume_vs_sma_20"] = (volume / vol_sma).where(vol_sma > 0)
    direction = np.sign(close.diff()).fillna(0.0)
    obv = (direction * volume).cumsum()
    # OBV level is arbitrary; its recent change relative to recent traded volume is not.
    feats["obv_change_24"] = ((obv - obv.shift(24)) / volume.rolling(24, min_periods=24).sum()).where(
        volume.rolling(24, min_periods=24).sum() > 0
    )
    typical = (high + low + close) / 3.0
    pv = (typical * volume).rolling(24, min_periods=24).sum()
    vv = volume.rolling(24, min_periods=24).sum()
    vwap = (pv / vv).where(vv > 0)
    feats["close_vs_vwap_24"] = close / vwap - 1.0

    # Causal support / resistance proxies --------------------------------------
    w = cfg.sr_window
    roll_low = low.rolling(w, min_periods=w).min()
    roll_high = high.rolling(w, min_periods=w).max()
    feats["dist_to_support"] = close / roll_low - 1.0
    feats["dist_to_resistance"] = roll_high / close - 1.0

    # Trend classification: reuse classify_trend per bar with causal inputs -------
    sma_50 = sma_last.get(50, np.full(n, np.nan))
    sma_200 = sma_last.get(200, np.full(n, np.nan))
    trend = np.zeros(n, dtype="float64")
    trend_valid = np.zeros(n, dtype=bool)
    for i in range(n):
        prev_h = macd_hist[i - 1] if i > 0 else np.nan
        cur_h = macd_hist[i]
        state = ind.MacdCrossover.NONE
        if not (np.isnan(prev_h) or np.isnan(cur_h)):
            if prev_h <= 0 < cur_h:
                state = ind.MacdCrossover.BULLISH
            elif prev_h >= 0 > cur_h:
                state = ind.MacdCrossover.BEARISH
        # Same requirement the Phase 10 service has: need an RSI and SMA-50 to say anything.
        if np.isnan(rsi[i]) or np.isnan(sma_50[i]):
            trend[i] = np.nan
            continue
        label = ind.classify_trend(
            last_close=c[i],
            sma_50=None if np.isnan(sma_50[i]) else float(sma_50[i]),
            sma_200=None if np.isnan(sma_200[i]) else float(sma_200[i]),
            macd_state=state,
            rsi_value=float(rsi[i]),
        )
        trend[i] = _TREND_CODE[label.value]
        trend_valid[i] = True
    feats["trend_code"] = trend

    out = pd.DataFrame({k: (v.to_numpy() if isinstance(v, pd.Series) else v) for k, v in feats.items()}, index=idx)
    return out.replace([np.inf, -np.inf], np.nan)
