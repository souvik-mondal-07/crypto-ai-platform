from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from ml.data.loaders import candles_from_klines, candles_from_records, interval_to_seconds
from ml.data.preprocessing import clean_candles, drop_incomplete_last_candle
from ml.data.validation import validate_candles
from ml.tests.conftest import make_candles


def test_klines_are_parsed_and_malformed_rows_skipped():
    rows = [
        [1735689600000, "100", "110", "90", "105", "12.5", 1735693199999],
        ["bad", "x"],
        [1735693200000, "105", "111", "99", "108", "7", 1735696799999],
    ]
    df = candles_from_klines(rows)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["timestamp"].iloc[0] == pd.Timestamp("2025-01-01 00:00:00", tz="UTC")
    assert df["close"].tolist() == [105.0, 108.0]


def test_records_missing_columns_rejected():
    with pytest.raises(ValueError):
        candles_from_records([{"timestamp": "2025-01-01", "open": 1}])


def test_unknown_interval_rejected():
    with pytest.raises(ValueError):
        interval_to_seconds("3h")


def test_sorting_is_chronological_and_reported():
    df = make_candles(50).sample(frac=1.0, random_state=3)
    out, report = clean_candles(df, 3600)
    assert out["timestamp"].is_monotonic_increasing
    assert report.reordered is True
    assert len(out) == 50


def test_duplicates_keep_last_occurrence():
    df = make_candles(10)
    dup = df.iloc[[4]].copy()
    dup["close"] = df["close"].iloc[4] * 1.0001
    dup["high"] = df["high"].iloc[4] * 1.01
    out, report = clean_candles(pd.concat([df, dup]), 3600)
    assert report.dropped_duplicates == 1
    assert len(out) == 10
    assert out.loc[out["timestamp"] == df["timestamp"].iloc[4], "close"].iloc[0] == pytest.approx(dup["close"].iloc[0])


def test_invalid_rows_are_dropped_not_repaired():
    df = make_candles(20)
    df.loc[3, "close"] = np.nan             # missing value
    df.loc[5, "open"] = -1.0                # non-positive
    df.loc[7, ["high", "low"]] = [90.0, 95.0]  # high < low
    df.loc[9, "volume"] = -5.0              # negative volume
    df.loc[11, "close"] = np.inf
    out, report = clean_candles(df, 3600)
    assert len(out) == 20 - 5
    assert report.dropped_unparseable + report.dropped_invalid_values == 5
    assert np.isfinite(out[["open", "high", "low", "close"]].to_numpy()).all()


def test_gaps_are_reported_but_never_filled():
    df = make_candles(30).drop(index=[10, 11, 20])
    out, report = clean_candles(df, 3600)
    assert len(out) == 27                    # nothing was invented
    assert report.gap_count == 2
    assert report.max_gap_candles == 2


def test_missing_columns_raise():
    with pytest.raises(ValueError):
        clean_candles(pd.DataFrame({"timestamp": [1], "close": [1.0]}))


def test_incomplete_last_candle_is_dropped():
    df = make_candles(10)
    last_open = df["timestamp"].iloc[-1]
    inside = (last_open + timedelta(minutes=20)).to_pydatetime()
    assert len(drop_incomplete_last_candle(df, 3600, inside)) == 9
    after = (last_open + timedelta(hours=1, seconds=1)).to_pydatetime()
    assert len(drop_incomplete_last_candle(df, 3600, after)) == 10
    assert drop_incomplete_last_candle(df.iloc[0:0], 3600).empty


def test_validation_statuses():
    df, report = clean_candles(make_candles(300), 3600)
    assert validate_candles(df, interval_seconds=3600, min_rows=500).status == "insufficient_data"
    assert validate_candles(df, interval_seconds=3600, min_rows=100, report=report).status == "ok"
    now = (df["timestamp"].iloc[-1] + timedelta(days=10)).to_pydatetime()
    stale = validate_candles(df, interval_seconds=3600, min_rows=100, max_staleness_candles=5, now=now)
    assert stale.status == "invalid"
    broken = df.iloc[::-1].reset_index(drop=True)
    assert validate_candles(broken, interval_seconds=3600, min_rows=100).status == "invalid"


def test_too_many_gaps_is_invalid():
    df = make_candles(300)
    df = df.drop(index=list(range(10, 300, 5)))
    clean, report = clean_candles(df, 3600)
    assert validate_candles(clean, interval_seconds=3600, min_rows=50, report=report).status == "invalid"
