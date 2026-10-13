"""Shared TEST fixtures.

The synthetic candle series below exist only inside the test-suite so the
pipeline can be exercised deterministically offline. Production code never
generates or substitutes data (see test_no_fake_data.py).
"""

import numpy as np
import pandas as pd
import pytest


def make_candles(n: int = 1500, seed: int = 0, ar: float = 0.0, interval: str = "1h", start: str = "2025-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    eps = rng.normal(0, 0.004, n)
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = ar * r[i - 1] + eps[i]
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.002, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.002, n))
    ts = pd.date_range(start, periods=n, freq=interval, tz="UTC")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low, "close": close,
                         "volume": rng.uniform(100, 1000, n)})


@pytest.fixture
def candles():
    return make_candles(1500, seed=1)


@pytest.fixture
def predictable_candles():
    # momentum (AR(1)) series: genuinely predictable from past returns
    return make_candles(3500, seed=7, ar=0.35)
