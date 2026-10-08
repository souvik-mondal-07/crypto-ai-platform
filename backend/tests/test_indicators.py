"""
Unit tests for app/services/indicators.py — pure calculation logic,
no MongoDB, no provider, no FastAPI. Uses synthetic price series with
known, verifiable properties (monotonic trends, fixed volatility)
rather than asserting exact floating-point values pulled from a
external reference implementation.
"""

import random

import pytest

from app.services import indicators as ind


def _uptrend(n=60, step=0.5):
    return [100 + i * step for i in range(n)]


def _downtrend(n=60, step=0.5):
    return [200 - i * step for i in range(n)]


def _noisy_series(n=60, seed=7):
    rnd = random.Random(seed)
    values = [100.0]
    for _ in range(n - 1):
        values.append(values[-1] + rnd.uniform(-3, 3))
    return values


class TestSMA:
    def test_returns_none_before_enough_history(self):
        result = ind.sma(_uptrend(30), 20)
        assert all(v is None for v in result[:19])
        assert result[19] is not None

    def test_too_few_values_returns_all_none(self):
        result = ind.sma([1.0, 2.0, 3.0], 20)
        assert result == [None, None, None]

    def test_matches_manual_average(self):
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = ind.sma(values, 3)
        assert result[2] == pytest.approx(20.0)  # avg(10,20,30)
        assert result[3] == pytest.approx(30.0)  # avg(20,30,40)
        assert result[4] == pytest.approx(40.0)  # avg(30,40,50)


class TestEMA:
    def test_returns_none_before_enough_history(self):
        result = ind.ema(_uptrend(30), 20)
        assert all(v is None for v in result[:19])
        assert result[19] is not None

    def test_tracks_a_steady_uptrend_upward(self):
        result = ind.ema(_uptrend(40), 10)
        defined = [v for v in result if v is not None]
        assert defined == sorted(defined)  # strictly non-decreasing


class TestRSI:
    def test_monotonic_uptrend_is_strongly_overbought(self):
        series = ind.rsi(_uptrend(40, step=2), period=14)
        assert series[-1] == pytest.approx(100.0)

    def test_monotonic_downtrend_is_strongly_oversold(self):
        series = ind.rsi(_downtrend(40, step=2), period=14)
        assert series[-1] == pytest.approx(0.0)

    def test_bounded_between_0_and_100(self):
        series = ind.rsi(_noisy_series(60), period=14)
        for v in series:
            if v is not None:
                assert 0.0 <= v <= 100.0

    def test_insufficient_history_returns_all_none(self):
        assert ind.rsi([1.0, 2.0, 3.0], period=14) == [None, None, None]

    def test_zone_classification(self):
        assert ind.rsi_zone(80.0) == ind.RsiZone.OVERBOUGHT
        assert ind.rsi_zone(20.0) == ind.RsiZone.OVERSOLD
        assert ind.rsi_zone(50.0) == ind.RsiZone.NEUTRAL
        assert ind.rsi_zone(None) is None


class TestMACD:
    def test_length_matches_input(self):
        closes = _noisy_series(60)
        points = ind.macd(closes)
        assert len(points) == len(closes)

    def test_histogram_is_macd_minus_signal(self):
        points = ind.macd(_noisy_series(60))
        for p in points:
            if p.macd is not None and p.signal is not None:
                assert p.histogram == pytest.approx(p.macd - p.signal)

    def test_crossover_detects_histogram_sign_flip(self):
        # Construct a MACD point series with an explicit sign flip.
        points = [
            ind.MacdPoint(macd=1.0, signal=1.5, histogram=-0.5),
            ind.MacdPoint(macd=1.0, signal=0.5, histogram=0.5),
        ]
        assert ind.macd_crossover(points) == ind.MacdCrossover.BULLISH

        points_bearish = [
            ind.MacdPoint(macd=1.0, signal=0.5, histogram=0.5),
            ind.MacdPoint(macd=1.0, signal=1.5, histogram=-0.5),
        ]
        assert ind.macd_crossover(points_bearish) == ind.MacdCrossover.BEARISH

    def test_no_crossover_when_sign_unchanged(self):
        points = [
            ind.MacdPoint(macd=1.0, signal=0.5, histogram=0.5),
            ind.MacdPoint(macd=1.2, signal=0.6, histogram=0.6),
        ]
        assert ind.macd_crossover(points) == ind.MacdCrossover.NONE


class TestBollingerBands:
    def test_upper_middle_lower_ordering(self):
        points = ind.bollinger_bands(_noisy_series(60), period=20, num_std_dev=2.0)
        for p in points:
            if p.middle is not None:
                assert p.upper > p.middle > p.lower

    def test_zero_volatility_collapses_bands_to_the_price(self):
        flat = [100.0] * 30
        points = ind.bollinger_bands(flat, period=20, num_std_dev=2.0)
        last = points[-1]
        assert last.upper == pytest.approx(100.0)
        assert last.middle == pytest.approx(100.0)
        assert last.lower == pytest.approx(100.0)


class TestATR:
    def _candles(self, closes):
        return [
            ind.Candle(timestamp=str(i), open=c, high=c + 2, low=c - 2, close=c)
            for i, c in enumerate(closes)
        ]

    def test_positive_when_there_is_a_high_low_range(self):
        series = ind.atr(self._candles(_noisy_series(40)), period=14)
        assert series[-1] is not None and series[-1] > 0

    def test_insufficient_candles_returns_all_none(self):
        series = ind.atr(self._candles([100.0, 101.0, 102.0]), period=14)
        assert all(v is None for v in series)


class TestSupportResistance:
    def test_returns_at_most_max_levels_each_side(self):
        candles = [
            ind.Candle(timestamp=str(i), open=c, high=c + 1, low=c - 1, close=c)
            for i, c in enumerate(_noisy_series(80))
        ]
        result = ind.support_resistance(candles, window=5, max_levels=3)
        assert len(result.support) <= 3
        assert len(result.resistance) <= 3

    def test_too_short_series_returns_empty(self):
        candles = [
            ind.Candle(timestamp=str(i), open=100, high=101, low=99, close=100) for i in range(5)
        ]
        result = ind.support_resistance(candles, window=5)
        assert result.support == []
        assert result.resistance == []


class TestTrendClassification:
    def test_all_bullish_signals_yield_bullish(self):
        trend = ind.classify_trend(
            last_close=110,
            sma_50=100,
            sma_200=90,
            macd_state=ind.MacdCrossover.BULLISH,
            rsi_value=65,
        )
        assert trend == ind.Trend.BULLISH

    def test_all_bearish_signals_yield_bearish(self):
        trend = ind.classify_trend(
            last_close=90,
            sma_50=100,
            sma_200=110,
            macd_state=ind.MacdCrossover.BEARISH,
            rsi_value=35,
        )
        assert trend == ind.Trend.BEARISH

    def test_no_data_at_all_is_neutral(self):
        trend = ind.classify_trend(
            last_close=None, sma_50=None, sma_200=None, macd_state=ind.MacdCrossover.NONE, rsi_value=None
        )
        assert trend == ind.Trend.NEUTRAL

    def test_mixed_signals_can_net_to_neutral(self):
        # price above SMA50 (+1) but RSI oversold (-1) -> net 0
        trend = ind.classify_trend(
            last_close=105, sma_50=100, sma_200=None, macd_state=ind.MacdCrossover.NONE, rsi_value=25
        )
        assert trend == ind.Trend.NEUTRAL
