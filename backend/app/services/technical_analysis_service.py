"""
Technical analysis service — business logic for RSI/MACD/moving
averages/Bollinger Bands/ATR/volume/support-resistance/trend.

Architecture (per Phase 10 brief):

    Providers (CoinGecko price OHLC + Binance historical volume OHLCV)
            v
    TechnicalAnalysisService (this file)
            v
    TechnicalAnalysisRepository
            v
    FastAPI routes

Indicator math lives in app/services/indicators.py as pure functions;
this service is only responsible for resolving the coin, fetching real
historical data, calling those functions, caching the result, and
shaping the response schema. Routes never touch the repository,
provider, or indicators module directly.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.providers.coingecko import CoinGeckoProvider
from app.providers.binance.provider import BinanceProvider
from app.providers.normalized import NormalizedCandle
from app.providers.errors import ProviderError
from app.providers.timeframes import Timeframe
from app.repositories.coin_repository import CoinRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.technical_analysis_repository import TechnicalAnalysisRepository
from app.schemas.technical_analysis import (
    AtrData,
    BollingerBandsData,
    HistoricalVolumePoint,
    MacdData,
    MacdPointSchema,
    MovingAverages,
    RsiData,
    SupportResistanceData,
    TechnicalAnalysisResponse,
    TrendAnalysis,
    VolumeAnalysis,
)
from app.services import indicators

logger = logging.getLogger("crypto_ai_platform.services.technical_analysis")

DATA_SOURCE = "coingecko"

# Minimum candles required before any indicator is computed at all —
# below this, "technical analysis" would mostly be null fields, which
# is a worse response than a clear "not enough data yet" error.
MIN_CANDLES_REQUIRED = 20

# How long a cached snapshot is considered fresh before being
# recomputed. Technical analysis is derived from data that itself
# only updates on the order of minutes (see market-data.md), so a
# short cache avoids recalculating on every page load without serving
# stale numbers for long.
CACHE_TTL_SECONDS = 300

RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
SMA_PERIODS = [20, 50, 200]
EMA_PERIODS = [20, 50]
BOLLINGER_PERIOD = 20
BOLLINGER_STD_DEV = 2.0
ATR_PERIOD = 14


class TechnicalAnalysisService:
    def __init__(
        self,
        coin_repository: Optional[CoinRepository] = None,
        market_data_repository: Optional[MarketDataRepository] = None,
        technical_analysis_repository: Optional[TechnicalAnalysisRepository] = None,
        coingecko_provider: Optional[CoinGeckoProvider] = None,
        binance_provider: Optional[BinanceProvider] = None,
    ) -> None:
        self._coins = coin_repository or CoinRepository()
        self._market_data = market_data_repository or MarketDataRepository()
        self._technical_analysis = technical_analysis_repository or TechnicalAnalysisRepository()
        self._coingecko = coingecko_provider or CoinGeckoProvider()
        self._binance = binance_provider or BinanceProvider()

    async def get_technical_analysis(
        self, coin_id: str, timeframe: Timeframe, force_refresh: bool = False
    ) -> TechnicalAnalysisResponse:
        if not ObjectId.is_valid(coin_id):
            raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        object_id = ObjectId(coin_id)

        coin_doc = await self._coins.find_by_internal_id(coin_id)
        if coin_doc is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")

        if not force_refresh:
            cached = await self._technical_analysis.get_latest(object_id, timeframe.value)
            if cached is not None and not TechnicalAnalysisRepository.is_stale(cached, CACHE_TTL_SECONDS):
                return _doc_to_response(cached)

        provider_coin_id = (coin_doc.get("providers") or {}).get("coingecko", {}).get("id")
        if not provider_coin_id:
            raise AppError(
                404, "TECHNICAL_ANALYSIS_NOT_AVAILABLE",
                "This coin has no provider mapping that can supply historical data.",
            )

        if not self._coingecko.supports_historical_ohlc:
            raise AppError(
                503, "TECHNICAL_ANALYSIS_NOT_AVAILABLE",
                "Historical data is not available from the current provider.",
            )

        try:
            raw_candles = await self._coingecko.get_historical_ohlc(provider_coin_id, timeframe)
        except ProviderError:
            # Propagates to the registered ProviderError handler
            # (app/core/exceptions.py) -> clean 503/504/429.
            raise

        if len(raw_candles) < MIN_CANDLES_REQUIRED:
            raise AppError(
                422, "INSUFFICIENT_HISTORICAL_DATA",
                f"Only {len(raw_candles)} candles are available for timeframe '{timeframe.value}'; "
                f"at least {MIN_CANDLES_REQUIRED} are needed to compute technical analysis.",
            )

        candles = [
            indicators.Candle(
                timestamp=c.timestamp, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume
            )
            for c in raw_candles
        ]
        closes = [c.close for c in candles]

        binance_symbol = (coin_doc.get("providers") or {}).get("binance", {}).get("symbol")
        volume_candles = []
        if binance_symbol:
            try:
                volume_candles = await self._binance.get_historical_ohlcv(binance_symbol, timeframe)
            except ProviderError:
                logger.warning("Binance historical volume unavailable for %s", binance_symbol, exc_info=True)

        response = await self._compute(
            coin_id=coin_id,
            symbol=coin_doc.get("symbol", ""),
            timeframe=timeframe,
            candles=candles,
            closes=closes,
            volume_candles=volume_candles,
        )

        await self._technical_analysis.upsert(
            object_id, timeframe.value, _response_to_doc(response)
        )
        return response

    async def _compute(
        self,
        *,
        coin_id: str,
        symbol: str,
        timeframe: Timeframe,
        candles: list[indicators.Candle],
        closes: list[float],
        volume_candles: Optional[list[NormalizedCandle]] = None,
    ) -> TechnicalAnalysisResponse:
        timestamps = [c.timestamp.isoformat() for c in candles]

        # RSI
        rsi_series = indicators.rsi(closes, RSI_PERIOD)
        current_rsi = rsi_series[-1]
        rsi_data = RsiData(
            period=RSI_PERIOD,
            current=current_rsi,
            zone=indicators.rsi_zone(current_rsi).value if indicators.rsi_zone(current_rsi) else None,
            history=rsi_series,
        )

        # MACD
        macd_points = indicators.macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
        macd_crossover = indicators.macd_crossover(macd_points)
        macd_data = MacdData(
            fast_period=MACD_FAST,
            slow_period=MACD_SLOW,
            signal_period=MACD_SIGNAL,
            current=MacdPointSchema(
                timestamp=timestamps[-1],
                macd=macd_points[-1].macd,
                signal=macd_points[-1].signal,
                histogram=macd_points[-1].histogram,
            ),
            crossover=macd_crossover.value,
            history=[
                MacdPointSchema(timestamp=ts, macd=p.macd, signal=p.signal, histogram=p.histogram)
                for ts, p in zip(timestamps, macd_points)
            ],
        )

        # Moving averages — only periods with enough history are populated;
        # others are simply omitted (not fabricated).
        sma_values: dict[str, Optional[float]] = {}
        for period in SMA_PERIODS:
            series = indicators.sma(closes, period)
            sma_values[str(period)] = series[-1] if len(closes) >= period else None
        ema_values: dict[str, Optional[float]] = {}
        for period in EMA_PERIODS:
            series = indicators.ema(closes, period)
            ema_values[str(period)] = series[-1] if len(closes) >= period else None
        moving_averages = MovingAverages(sma=sma_values, ema=ema_values)

        # Bollinger Bands
        bb_points = indicators.bollinger_bands(closes, BOLLINGER_PERIOD, BOLLINGER_STD_DEV)
        last_bb = bb_points[-1]
        bollinger = BollingerBandsData(
            period=BOLLINGER_PERIOD,
            num_std_dev=BOLLINGER_STD_DEV,
            upper=last_bb.upper,
            middle=last_bb.middle,
            lower=last_bb.lower,
        )

        # ATR
        atr_series = indicators.atr(candles, ATR_PERIOD)
        atr_data = AtrData(period=ATR_PERIOD, current=atr_series[-1], history=atr_series)

        # Volume — real data only; see VolumeAnalysis docstring for why
        # a historical trend isn't offered.
        volume_data = await self._volume_analysis(coin_id, volume_candles or [])

        # Support / resistance
        sr = indicators.support_resistance(candles)
        support_resistance = SupportResistanceData(
            support_levels=sr.support, resistance_levels=sr.resistance
        )

        # Trend classification
        trend = indicators.classify_trend(
            last_close=closes[-1],
            sma_50=sma_values.get("50"),
            sma_200=sma_values.get("200"),
            macd_state=macd_crossover,
            rsi_value=current_rsi,
        )
        signals_available = sum(
            1
            for v in [
                sma_values.get("50") is not None and closes[-1] is not None,
                sma_values.get("50") is not None and sma_values.get("200") is not None,
                macd_crossover != indicators.MacdCrossover.NONE,
                current_rsi is not None,
            ]
            if v
        )
        trend_data = TrendAnalysis(trend=trend.value, signals_considered=signals_available)

        return TechnicalAnalysisResponse(
            coin_id=coin_id,
            symbol=symbol,
            timeframe=timeframe.value,
            calculated_at=datetime.now(timezone.utc),
            candle_count=len(candles),
            rsi=rsi_data,
            macd=macd_data,
            moving_averages=moving_averages,
            bollinger_bands=bollinger,
            atr=atr_data,
            volume=volume_data,
            support_resistance=support_resistance,
            trend=trend_data,
            data_source=DATA_SOURCE,
        )

    async def _volume_analysis(self, coin_id: str, candles: list[NormalizedCandle]) -> VolumeAnalysis:
        """Use Binance kline base-asset volumes; compare last 10 vs preceding 10.

        Trend threshold is +/-10% to avoid labeling small fluctuations as meaningful.
        This describes volume only and is not a price-direction signal.
        """
        current = None
        if ObjectId.is_valid(coin_id):
            market_doc = await self._market_data.get_by_coin_id(ObjectId(coin_id))
            if market_doc:
                v = market_doc.get("volume_24h_usd")
                if isinstance(v, (int, float)) and math.isfinite(v) and v >= 0: current = float(v)
        valid = [c for c in candles if c.volume is not None and isinstance(c.volume, (int,float)) and math.isfinite(c.volume) and c.volume >= 0]
        points = [HistoricalVolumePoint(timestamp=c.timestamp, volume=float(c.volume)) for c in valid]
        if len(valid) < 20:
            return VolumeAnalysis(current_volume_24h_usd=current, historical_volume=points,
                                 historical_volume_source="binance" if points else None)
        prev = sum(c.volume for c in valid[-20:-10]) / 10
        recent = sum(c.volume for c in valid[-10:]) / 10
        if prev <= 0:
            return VolumeAnalysis(current_volume_24h_usd=current, historical_volume=points,
                                 average_volume=recent, historical_volume_source="binance")
        change = (recent-prev)/prev*100
        trend = "increasing" if change > 10 else "decreasing" if change < -10 else "neutral"
        return VolumeAnalysis(current_volume_24h_usd=current, historical_volume=points, average_volume=recent,
                              volume_change_percent=change, trend=trend, historical_volume_source="binance")


def _response_to_doc(response: TechnicalAnalysisResponse) -> dict:
    """Storage shape matching docs/database-schema.md's `technical_analysis` collection."""
    return {
        "symbol": response.symbol,
        "timestamp": response.calculated_at,
        "calculated_at": response.calculated_at,
        "candle_count": response.candle_count,
        "rsi": response.rsi.current,
        "macd": {
            "macd": response.macd.current.macd,
            "signal": response.macd.current.signal,
            "histogram": response.macd.current.histogram,
        },
        "sma": response.moving_averages.sma,
        "ema": response.moving_averages.ema,
        "bollinger_bands": {
            "upper": response.bollinger_bands.upper,
            "middle": response.bollinger_bands.middle,
            "lower": response.bollinger_bands.lower,
        },
        "atr": response.atr.current,
        "volume": response.volume.model_dump(),
        "support_levels": response.support_resistance.support_levels,
        "resistance_levels": response.support_resistance.resistance_levels,
        "trend": response.trend.trend,
        "source": response.data_source,
        # Full response payload cached verbatim too, so a cache hit
        # can rebuild the exact same response (including RSI/MACD/ATR
        # history arrays for charting) without recomputation.
        "_full_response": response.model_dump(mode="json"),
    }


def _doc_to_response(doc: dict) -> TechnicalAnalysisResponse:
    return TechnicalAnalysisResponse(**doc["_full_response"])
