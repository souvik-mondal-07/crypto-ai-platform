"""
Market service — business logic for current market data, overview,
gainers/losers, global stats, trending coins, and historical OHLC.

Routes call this, never the repository or a provider client directly.
"""

import logging
from datetime import datetime
from typing import Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.providers.binance import BinanceProvider
from app.providers.coingecko import CoinGeckoProvider
from app.providers.errors import ProviderError
from app.repositories.coin_repository import CoinRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.converters import (
    coin_doc_to_schema,
    is_snapshot_stale,
    market_data_doc_to_schema,
    mover_item,
    volatility_24h_pct,
)
from app.providers.timeframes import TIMEFRAME_GRANULARITY, Timeframe
from app.schemas.market import (
    GlobalMarket,
    HistoricalCandle,
    HistoricalPriceResponse,
    MarketData,
    ExchangeTicker,
    ExchangeTickerResponse,
    MarketCoin,
    MarketCoinListResponse,
    MarketOverview,
    MoverItem,
    TrendingCoin,
    TrendingResponse,
)
from app.utils.pagination import clamp_pagination, total_pages

logger = logging.getLogger("crypto_ai_platform.services.market")

DATA_SOURCE = "coingecko"

#: Whitelist for ranking endpoints — a client-supplied string is never
#: passed into a MongoDB sort spec (same rule as CoinRepository's
#: SORTABLE_FIELDS).
RANKABLE_FIELDS: dict[str, str] = {
    "market_cap": "market_cap_usd",
    "volume": "volume_24h_usd",
}

#: Sortable fields for the joined Markets table. These live in
#: `market_data` (not `coins`), which is why that collection drives
#: the join — see MarketDataRepository.list_coins_with_market_data.
#: A client string is resolved through this map, never used directly.
MARKET_SORT_FIELDS: dict[str, str] = {
    "market_cap": "market_cap_usd",
    "price": "price_usd",
    "change_24h": "percent_change_24h",
    "volume": "volume_24h_usd",
    "change_7d": "percent_change_7d",
    "fdv": "fully_diluted_valuation_usd",
    "supply": "circulating_supply",
    # Computed in the aggregation from (24h high - low) / price.
    "volatility": "volatility_24h_pct",
}

#: Upper bound on `coin_ids` per request (watchlist / compare / trending).
MAX_COIN_IDS = 100

#: Filters expressible as bounds on 24h change. "all" applies none.
MARKET_FILTERS = {"all", "gainers", "losers"}


class MarketService:
    def __init__(
        self,
        coin_repository: Optional[CoinRepository] = None,
        market_data_repository: Optional[MarketDataRepository] = None,
        coingecko_provider: Optional[CoinGeckoProvider] = None,
        binance_provider: Optional[BinanceProvider] = None,
    ) -> None:
        self._coins = coin_repository or CoinRepository()
        self._market_data = market_data_repository or MarketDataRepository()
        self._coingecko = coingecko_provider or CoinGeckoProvider()
        self._binance = binance_provider or BinanceProvider()

    async def get_coin_market_data(self, coin_id: str) -> MarketData:
        if not ObjectId.is_valid(coin_id):
            raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        object_id = ObjectId(coin_id)

        coin_doc = await self._coins.find_by_internal_id(coin_id)
        if coin_doc is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")

        market_doc = await self._market_data.get_by_coin_id(object_id)
        if market_doc is None:
            raise AppError(
                404, "MARKET_DATA_NOT_AVAILABLE",
                f"No market data has been synced yet for coin '{coin_id}'.",
            )
        return market_data_doc_to_schema(market_doc)

    async def get_top_movers(self, direction: str, limit: int) -> list:
        _, safe_limit = clamp_pagination(1, min(limit, 100))
        market_docs = await self._market_data.get_top_movers(direction, safe_limit)
        if not market_docs:
            return []

        coin_ids = [doc["coin_id"] for doc in market_docs]
        coins_by_id = await self._coins.find_by_internal_ids(coin_ids)

        results = []
        for market_doc in market_docs:
            coin_doc = coins_by_id.get(market_doc["coin_id"])
            if coin_doc is None:
                # Market data exists for a coin that's since been
                # removed/deactivated — skip rather than error, since
                # this is an expected transient state, not a bug.
                continue
            results.append(mover_item(coin_doc, market_doc))
        return results

    async def get_overview(self, movers_limit: int = 5) -> MarketOverview:
        gainers = await self.get_top_movers("gainers", movers_limit)
        losers = await self.get_top_movers("losers", movers_limit)
        active_count = await self._coins.count_active()
        last_updated = await self._market_data.most_recent_update()

        return MarketOverview(
            active_cryptocurrencies=active_count,
            top_gainers=gainers,
            top_losers=losers,
            last_updated=last_updated,
            data_source=DATA_SOURCE,
        )

    async def get_global_market(self) -> GlobalMarket:
        try:
            normalized = await self._coingecko.get_global_market()
        except ProviderError:
            # Let the registered ProviderError handler in
            # app/core/exceptions.py translate this into a clean
            # 503/504/etc response — the route/service layer doesn't
            # need its own try/except duplicate of that mapping.
            raise

        if normalized is None:
            raise AppError(
                503, "GLOBAL_MARKET_UNAVAILABLE",
                "Global market statistics are not available from the current provider.",
            )

        return GlobalMarket(
            total_market_cap_usd=normalized.total_market_cap_usd,
            total_volume_24h_usd=normalized.total_volume_24h_usd,
            market_cap_percentage=normalized.market_cap_percentage,
            active_cryptocurrencies=normalized.active_cryptocurrencies,
            market_cap_change_percentage_24h=normalized.market_cap_change_percentage_24h,
            last_updated=normalized.last_updated,
            data_source=DATA_SOURCE,
        )

    async def get_trending(self) -> TrendingResponse:
        if not self._coingecko.supports_trending:
            return TrendingResponse(items=[], available=False, data_source=DATA_SOURCE)

        try:
            normalized_items = await self._coingecko.get_trending()
        except ProviderError:
            raise

        # Best-effort match against our own coin collection so the
        # frontend can link straight to a coin detail page where
        # possible — a trending coin we haven't synced yet is still
        # returned, just without an internal_coin_id.
        items = []
        for entry in normalized_items:
            coin_doc = await self._coins.find_by_coingecko_id(entry.coingecko_id)
            items.append(
                TrendingCoin(
                    coingecko_id=entry.coingecko_id,
                    internal_coin_id=str(coin_doc["_id"]) if coin_doc else None,
                    name=entry.name,
                    symbol=entry.symbol,
                    market_cap_rank=entry.market_cap_rank,
                    score=entry.score,
                )
            )
        return TrendingResponse(items=items, available=True, data_source=DATA_SOURCE)

    async def get_coin_history(self, coin_id: str, timeframe: Timeframe) -> HistoricalPriceResponse:
        """
        Historical OHLC candles for one coin.

        Resolves the platform's internal coin ID to the provider's own
        coin ID before calling the provider — the symbol is never used
        as a provider identifier (see docs/market-data.md on why
        symbols aren't unique).

        Fetched live from the provider rather than read from the
        `historical_prices` collection: no sync job populates that
        collection yet (it's still schema-only — see
        docs/database-schema.md), so reading from it would return
        nothing. Persisting candles is a separate concern from
        rendering a chart, and is left for the step that actually
        builds that ingestion.
        """
        if not ObjectId.is_valid(coin_id):
            raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")

        coin_doc = await self._coins.find_by_internal_id(coin_id)
        if coin_doc is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")

        provider_coin_id = (coin_doc.get("providers") or {}).get("coingecko", {}).get("id")
        if not provider_coin_id:
            raise AppError(
                404, "HISTORY_NOT_AVAILABLE",
                "This coin has no provider mapping that can supply historical data.",
            )

        if not self._coingecko.supports_historical_ohlc:
            raise AppError(
                503, "HISTORY_NOT_AVAILABLE",
                "Historical data is not available from the current provider.",
            )

        # ProviderError propagates to the handlers registered in
        # app/core/exceptions.py, which map it to a clean 503/504/429.
        candles = await self._coingecko.get_historical_ohlc(provider_coin_id, timeframe)

        return HistoricalPriceResponse(
            coin_id=coin_id,
            timeframe=timeframe.value,
            granularity=TIMEFRAME_GRANULARITY[timeframe],
            candles=[
                HistoricalCandle(
                    timestamp=candle.timestamp,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
                for candle in candles
            ],
            data_source=DATA_SOURCE,
        )

    async def get_top_ranked(self, ranking: str, limit: int) -> list[MoverItem]:
        """
        Highest coins by market cap or 24h volume, from synced market
        data. `ranking` must be a RANKABLE_FIELDS key — anything else
        is rejected rather than reaching MongoDB.
        """
        field = RANKABLE_FIELDS.get(ranking)
        if field is None:
            raise AppError(
                400, "INVALID_RANKING",
                f"ranking must be one of: {', '.join(sorted(RANKABLE_FIELDS))}.",
            )

        _, safe_limit = clamp_pagination(1, min(limit, 100))
        market_docs = await self._market_data.get_top_by_field(field, safe_limit)
        if not market_docs:
            return []

        coin_ids = [doc["coin_id"] for doc in market_docs]
        coins_by_id = await self._coins.find_by_internal_ids(coin_ids)

        results = []
        for market_doc in market_docs:
            coin_doc = coins_by_id.get(market_doc["coin_id"])
            if coin_doc is None:
                # Market data for a coin since removed/deactivated —
                # skip rather than error (same handling as movers).
                continue
            results.append(mover_item(coin_doc, market_doc))
        return results

    async def get_exchange_tickers(self, limit: int) -> ExchangeTickerResponse:
        """
        Binance's 24h stats for its USDT pairs — exchange-specific
        data, explicitly labelled as such so a caller can't mistake a
        single venue's price for the cross-market aggregate served by
        /coins/{id}/market.
        """
        _, safe_limit = clamp_pagination(1, min(limit, 250))
        normalized = await self._binance.get_exchange_tickers()

        # Highest quote-volume pairs first — the most liquid/meaningful
        # subset when a limit is applied. None sorts last.
        normalized.sort(key=lambda t: (t.quote_volume_24h is None, -(t.quote_volume_24h or 0.0)))

        tickers = [
            ExchangeTicker(
                symbol=t.symbol,
                base_asset=t.base_asset,
                quote_asset=t.quote_asset,
                last_price=t.last_price,
                price_change_percent_24h=t.price_change_percent_24h,
                high_24h=t.high_24h,
                low_24h=t.low_24h,
                volume_24h=t.volume_24h,
                quote_volume_24h=t.quote_volume_24h,
            )
            for t in normalized[:safe_limit]
        ]
        return ExchangeTickerResponse(exchange="binance", tickers=tickers, count=len(tickers))

    async def list_market_coins(
        self,
        *,
        page: int,
        limit: int,
        sort_by: str = "market_cap",
        sort_direction: str = "desc",
        market_filter: str = "all",
        change_min: Optional[float] = None,
        change_max: Optional[float] = None,
        market_cap_min: Optional[float] = None,
        market_cap_max: Optional[float] = None,
        volume_min: Optional[float] = None,
        volume_max: Optional[float] = None,
        has_max_supply: Optional[bool] = None,
        coin_ids: Optional[list[str]] = None,
    ) -> MarketCoinListResponse:
        """
        Paginated Markets-table rows: coins joined with their current
        market snapshot, sorted by a market field.

        Validates every client-supplied knob against a whitelist before
        anything reaches MongoDB.
        """
        field = MARKET_SORT_FIELDS.get(sort_by)
        if field is None:
            raise AppError(
                400, "INVALID_SORT_FIELD",
                f"sort_by must be one of: {', '.join(sorted(MARKET_SORT_FIELDS))}.",
            )
        if sort_direction not in ("asc", "desc"):
            raise AppError(400, "INVALID_SORT_DIRECTION", "sort_direction must be 'asc' or 'desc'.")
        if market_filter not in MARKET_FILTERS:
            raise AppError(
                400, "INVALID_FILTER",
                f"filter must be one of: {', '.join(sorted(MARKET_FILTERS))}.",
            )

        for label, low, high in (
            ("change", change_min, change_max),
            ("market_cap", market_cap_min, market_cap_max),
            ("volume", volume_min, volume_max),
        ):
            if low is not None and high is not None and low > high:
                raise AppError(400, "INVALID_RANGE", f"{label}_min must not exceed {label}_max.")
        for label, value in (
            ("market_cap_min", market_cap_min), ("market_cap_max", market_cap_max),
            ("volume_min", volume_min), ("volume_max", volume_max),
        ):
            if value is not None and value < 0:
                raise AppError(400, "INVALID_RANGE", f"{label} must not be negative.")

        object_ids: Optional[list[ObjectId]] = None
        if coin_ids is not None:
            if len(coin_ids) > MAX_COIN_IDS:
                raise AppError(400, "TOO_MANY_COIN_IDS", f"coin_ids accepts at most {MAX_COIN_IDS} ids.")
            if any(not ObjectId.is_valid(value) for value in coin_ids):
                raise AppError(400, "INVALID_COIN_ID", "coin_ids contains an invalid identifier.")
            object_ids = [ObjectId(value) for value in coin_ids]

        safe_page, safe_limit = clamp_pagination(page, limit)
        direction = 1 if sort_direction == "asc" else -1

        # Gainers/losers are expressed as bounds on 24h change rather
        # than a separate code path, so they compose with sorting,
        # pagination and the explicit change range like any other filter
        # (the tighter bound wins).
        lower_bounds = [b for b in (0.0 if market_filter == "gainers" else None, change_min) if b is not None]
        upper_bounds = [b for b in (0.0 if market_filter == "losers" else None, change_max) if b is not None]
        min_change = max(lower_bounds) if lower_bounds else None
        max_change = min(upper_bounds) if upper_bounds else None

        rows, total = await self._market_data.list_coins_with_market_data(
            skip=(safe_page - 1) * safe_limit,
            limit=safe_limit,
            sort_field=field,
            sort_direction=direction,
            min_change_24h=min_change,
            max_change_24h=max_change,
            min_market_cap=market_cap_min,
            max_market_cap=market_cap_max,
            min_volume=volume_min,
            max_volume=volume_max,
            has_max_supply=has_max_supply,
            coin_ids=object_ids,
        )

        # Freshness + universe size for the Markets header. Both are cheap
        # single-document / count queries. Guarded so a missing value is
        # reported as unknown (None) rather than guessed.
        raw_count = await self._market_data.count()
        coins_with_market_data = raw_count if isinstance(raw_count, int) else None
        raw_updated = await self._market_data.most_recent_update()
        last_updated = raw_updated if isinstance(raw_updated, datetime) else None

        items = [
            MarketCoin(
                coin_id=str(row["coin_id"]),
                name=row["coin"]["name"],
                symbol=row["coin"]["symbol"],
                logo_url=row["coin"].get("logo_url"),
                market_cap_rank=row["coin"].get("market_cap_rank"),
                price_usd=row.get("price_usd"),
                percent_change_24h=row.get("percent_change_24h"),
                high_24h_usd=row.get("high_24h_usd"),
                low_24h_usd=row.get("low_24h_usd"),
                market_cap_usd=row.get("market_cap_usd"),
                volume_24h_usd=row.get("volume_24h_usd"),
                circulating_supply=row.get("circulating_supply"),
                last_updated=row.get("last_updated"),
                percent_change_1h=row.get("percent_change_1h"),
                percent_change_7d=row.get("percent_change_7d"),
                percent_change_30d=row.get("percent_change_30d"),
                fully_diluted_valuation_usd=row.get("fully_diluted_valuation_usd"),
                total_supply=row.get("total_supply"),
                max_supply=row.get("max_supply"),
                ath_usd=row.get("ath_usd"),
                atl_usd=row.get("atl_usd"),
                ath_change_percentage=row.get("ath_change_percentage"),
                atl_change_percentage=row.get("atl_change_percentage"),
                volatility_24h_pct=row.get("volatility_24h_pct")
                if row.get("volatility_24h_pct") is not None
                else volatility_24h_pct(row.get("high_24h_usd"), row.get("low_24h_usd"), row.get("price_usd")),
                data_source=row.get("data_source"),
                is_stale=is_snapshot_stale(row.get("updated_at")),
            )
            for row in rows
        ]

        return MarketCoinListResponse(
            items=items,
            page=safe_page,
            limit=safe_limit,
            total=total,
            pages=total_pages(total, safe_limit),
            sort_by=sort_by,
            sort_direction=sort_direction,
            data_source=DATA_SOURCE,
            coins_with_market_data=coins_with_market_data,
            last_updated=last_updated,
            is_stale=is_snapshot_stale(last_updated),
        )
