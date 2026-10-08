"""Market features — scale-free transforms of OHLCV.

Every value at row ``t`` uses only candles ``<= t`` (trailing windows / lags).
Raw price levels (open/high/low/close) and raw volume are deliberately NOT fed to
the models: they are non-stationary (a tree model cannot extrapolate to prices it
never saw), so they are expressed as returns, ratios and z-scores instead. The raw
close stays in the dataset frame as metadata for converting a predicted return
back into a price range.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.config.feature_config import FeatureConfig


def build_market_features(candles: pd.DataFrame, cfg: FeatureConfig = FeatureConfig()) -> pd.DataFrame:
    close = candles["close"].astype("float64")
    open_ = candles["open"].astype("float64")
    high = candles["high"].astype("float64")
    low = candles["low"].astype("float64")
    volume = candles["volume"].astype("float64")

    feats: dict[str, pd.Series] = {}

    log_close = np.log(close)
    log_ret_1 = log_close.diff()
    feats["log_return_1"] = log_ret_1
    for w in cfg.return_windows:
        feats[f"return_{w}"] = close.pct_change(w)
    for w in cfg.volatility_windows:
        feats[f"volatility_{w}"] = log_ret_1.rolling(w, min_periods=w).std()

    feats["candle_range"] = (high - low) / close
    feats["candle_body"] = (close - open_) / open_
    feats["close_in_range"] = ((close - low) / (high - low)).where(high > low)
    feats["upper_wick"] = (high - np.maximum(open_, close)) / close
    feats["lower_wick"] = (np.minimum(open_, close) - low) / close

    log_vol = np.log1p(volume)
    feats["volume_change_1"] = log_vol.diff()
    for w in cfg.volume_windows:
        mean = log_vol.rolling(w, min_periods=w).mean()
        std = log_vol.rolling(w, min_periods=w).std()
        feats[f"volume_zscore_{w}"] = ((log_vol - mean) / std).where(std > 0)

    out = pd.DataFrame(feats, index=candles.index)
    return out.replace([np.inf, -np.inf], np.nan)
