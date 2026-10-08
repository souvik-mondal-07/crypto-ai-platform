"""
Centralized indexing strategy.

Indexes are created once at startup (after a successful connection),
not on every request. Each index below is tied to a concrete expected
query pattern — see docs/database-schema.md for the reasoning behind
each one and for which fields were deliberately left un-indexed.

Creating an index is idempotent: calling `create_index` with the same
keys/options on an existing index is a no-op, so it's safe to run this
on every startup.
"""

import logging

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.database.collections import CollectionName

logger = logging.getLogger("crypto_ai_platform.database")


async def initialize_indexes(db: AsyncDatabase) -> None:
    """
    Create all indexes required by current + near-term query patterns.

    Safe to call on every startup. Does not raise on failure — logs a
    clean warning instead, since a missing index should degrade query
    performance, not prevent the application from starting.
    """
    try:
        # users.email — unique, since email is the login identifier.
        # Created in Step 2 ahead of need; actively enforced as of
        # Step 4's registration/login. UserRepository always normalizes
        # (trim + lowercase) before every read/write, so the stored
        # `email` value is already normalized — a plain unique index on
        # the raw field correctly enforces uniqueness on that
        # normalized value without needing a separate indexed field.
        await db[CollectionName.USERS.value].create_index(
            "email", unique=True, name="uniq_users_email"
        )

        # coins: schema evolved in Step 3 — a coin now holds a
        # `providers` map (providers.coingecko.id, providers.binance.symbol)
        # instead of Step 2's flat (provider, provider_coin_id) fields,
        # since a single canonical coin can appear on multiple
        # providers at once. Drop the old Step 2 index if present
        # (safe/no-op if it was never created — no data was ever
        # written against it) before creating the new ones.
        try:
            await db[CollectionName.COINS.value].drop_index(
                "uniq_coins_provider_providercoinid"
            )
        except PyMongoError:
            pass  # index didn't exist — nothing to migrate

        # providers.coingecko.id is the uniqueness anchor: CoinGecko is
        # the broad-universe source of truth for Step 3, so every coin
        # is expected to have one. NOT unique on `symbol` — ticker
        # symbols collide across unrelated coins.
        await db[CollectionName.COINS.value].create_index(
            "providers.coingecko.id",
            unique=True,
            sparse=True,
            name="uniq_coins_providers_coingecko_id",
        )
        # Not unique: a delisted/relisted symbol on Binance, or a rare
        # provider inconsistency, shouldn't hard-fail a sync.
        await db[CollectionName.COINS.value].create_index(
            "providers.binance.symbol", name="idx_coins_providers_binance_symbol"
        )
        await db[CollectionName.COINS.value].create_index(
            "symbol", name="idx_coins_symbol"
        )
        await db[CollectionName.COINS.value].create_index(
            "name", name="idx_coins_name"
        )
        await db[CollectionName.COINS.value].create_index(
            "slug", name="idx_coins_slug"
        )
        await db[CollectionName.COINS.value].create_index(
            "market_cap_rank", name="idx_coins_marketcaprank"
        )
        await db[CollectionName.COINS.value].create_index(
            "is_active", name="idx_coins_isactive"
        )

        # Drop Step 2's compound (coin_id, timestamp) index — market_data
        # is now one upserted snapshot per coin, not a growing series.
        try:
            await db[CollectionName.MARKET_DATA.value].drop_index(
                "idx_marketdata_coin_timestamp"
            )
        except PyMongoError:
            pass

        # market_data (Step 3): one upserted "current snapshot" document
        # per coin (not a growing time series — see docs/market-data.md
        # for why this differs from historical_prices), so coin_id is
        # unique here rather than part of a compound time-range index.
        await db[CollectionName.MARKET_DATA.value].create_index(
            "coin_id", unique=True, name="uniq_marketdata_coinid"
        )
        # updated_at: supports "how stale is this snapshot" checks and
        # any future TTL/cleanup job.
        await db[CollectionName.MARKET_DATA.value].create_index(
            "updated_at", name="idx_marketdata_updatedat"
        )
        # percent_change_24h / market_cap: gainers/losers and
        # overview queries sort/filter on these directly.
        await db[CollectionName.MARKET_DATA.value].create_index(
            "percent_change_24h", name="idx_marketdata_percentchange24h"
        )
        await db[CollectionName.MARKET_DATA.value].create_index(
            "market_cap_usd", name="idx_marketdata_marketcapusd"
        )
        # price_usd / volume_24h_usd: the Markets table (Phase 8) sorts
        # on these server-side via /market/coins, so they need index
        # support for the same reason market_cap_usd does.
        await db[CollectionName.MARKET_DATA.value].create_index(
            "price_usd", name="idx_marketdata_priceusd"
        )
        await db[CollectionName.MARKET_DATA.value].create_index(
            "volume_24h_usd", name="idx_marketdata_volume24husd"
        )
        # FDV / circulating supply / 7d change: sortable columns of the
        # redesigned Markets table (same server-side sort rule as above).
        await db[CollectionName.MARKET_DATA.value].create_index(
            "fully_diluted_valuation_usd", name="idx_marketdata_fdvusd"
        )
        await db[CollectionName.MARKET_DATA.value].create_index(
            "circulating_supply", name="idx_marketdata_circulatingsupply"
        )
        await db[CollectionName.MARKET_DATA.value].create_index(
            "percent_change_7d", name="idx_marketdata_percentchange7d"
        )

        # historical_prices: range queries for a coin over time, per timeframe
        await db[CollectionName.HISTORICAL_PRICES.value].create_index(
            [
                ("coin_id", ASCENDING),
                ("timeframe", ASCENDING),
                ("timestamp", DESCENDING),
            ],
            name="idx_historicalprices_coin_timeframe_timestamp",
        )

        # news (Phase 12). The Step-2 index on a `coins` field was never
        # written against; drop it (no-op if absent) in favour of the
        # Phase 12 schema's `related_coin_ids`.
        try:
            await db[CollectionName.NEWS.value].drop_index("idx_news_coins_publishedat")
        except PyMongoError:
            pass
        news = db[CollectionName.NEWS.value]
        # Identity / deduplication: both keys must be unique.
        await news.create_index("news_id", unique=True, name="uniq_news_newsid")
        await news.create_index("dedupe_key", unique=True, name="uniq_news_dedupekey")
        # Global feed, newest first.
        await news.create_index([("published_at", DESCENDING)], name="idx_news_publishedat")
        # Coin feed + coin sentiment windows.
        await news.create_index(
            [("related_coin_ids", ASCENDING), ("published_at", DESCENDING)],
            name="idx_news_relatedcoinids_publishedat",
        )
        await news.create_index(
            [("source", ASCENDING), ("published_at", DESCENDING)], name="idx_news_source_publishedat"
        )
        await news.create_index("provider", name="idx_news_provider")
        # "Which articles still need sentiment" and sentiment-label filtering.
        await news.create_index(
            [("sentiment_status", ASCENDING), ("published_at", DESCENDING)],
            name="idx_news_sentimentstatus_publishedat",
        )
        await news.create_index(
            [("sentiment.label", ASCENDING), ("published_at", DESCENDING)],
            name="idx_news_sentimentlabel_publishedat",
        )

        # predictions: lookups by coin + horizon, most-recent-first
        await db[CollectionName.PREDICTIONS.value].create_index(
            [
                ("coin_id", ASCENDING),
                ("horizon", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_predictions_coin_horizon_createdat",
        )

        # Phase 13: the same `predictions` collection (no new collection) is
        # read as "latest prediction for a coin/horizon" and will later serve
        # history, so it is indexed on generated_at as well. expires_at is
        # deliberately NOT a TTL index — predictions are kept for history.
        await db[CollectionName.PREDICTIONS.value].create_index(
            [
                ("coin_id", ASCENDING),
                ("horizon", ASCENDING),
                ("generated_at", DESCENDING),
            ],
            name="idx_predictions_coin_horizon_generatedat",
        )
        await db[CollectionName.PREDICTIONS.value].create_index(
            [("generated_at", DESCENDING)], name="idx_predictions_generatedat"
        )

        # watchlists / alerts / analysis_history: all scoped per-user
        await db[CollectionName.WATCHLISTS.value].create_index(
            "user_id", name="idx_watchlists_user"
        )
        await db[CollectionName.ALERTS.value].create_index(
            "user_id", name="idx_alerts_user"
        )
        await db[CollectionName.ANALYSIS_HISTORY.value].create_index(
            "user_id", name="idx_analysishistory_user"
        )

        # model_metrics: lookups by model name, newest training run first
        await db[CollectionName.MODEL_METRICS.value].create_index(
            [("model_name", ASCENDING), ("training_timestamp", DESCENDING)],
            name="idx_modelmetrics_modelname_trainingtimestamp",
        )

        # technical_analysis (Phase 10): one upserted "latest snapshot"
        # document per (coin_id, timeframe) — same "current snapshot,
        # not a growing series" shape as market_data, and for the same
        # reason: recomputing is cheap, and every consumer (the Coin
        # Details UI, and future ML/prediction phases per
        # docs/database-schema.md) wants the latest values, not a
        # history of past calculations.
        await db[CollectionName.TECHNICAL_ANALYSIS.value].create_index(
            [("coin_id", ASCENDING), ("timeframe", ASCENDING)],
            unique=True,
            name="uniq_technicalanalysis_coin_timeframe",
        )
        await db[CollectionName.TECHNICAL_ANALYSIS.value].create_index(
            "calculated_at", name="idx_technicalanalysis_calculatedat"
        )

        # fundamental_analysis (Phase 11): one upserted document per coin.
        # The unique coin_id index is the only query pattern (lookup by
        # coin) and also guarantees the upsert can't create duplicates.
        await db[CollectionName.FUNDAMENTAL_ANALYSIS.value].create_index(
            "coin_id", unique=True, name="uniq_fundamentalanalysis_coinid"
        )

        # decisions (Phase 14): insert-only history, read as "latest decision for a coin" (and, later,
        # per engine version for backtesting). expires_at is deliberately NOT a TTL index.
        await db[CollectionName.DECISIONS.value].create_index(
            [("coin_id", ASCENDING), ("generated_at", DESCENDING)], name="idx_decisions_coin_generatedat"
        )
        await db[CollectionName.DECISIONS.value].create_index(
            [("engine_version", ASCENDING), ("generated_at", DESCENDING)],
            name="idx_decisions_engineversion_generatedat",
        )

        # ai_analysis (Phase 15): insert-only history of Gemini explanations, read as "latest analysis
        # for a coin"; prompt_version/model are indexed so later phases can compare prompt versions.
        # expires_at is deliberately NOT a TTL index.
        await db[CollectionName.AI_ANALYSIS.value].create_index(
            [("coin_id", ASCENDING), ("generated_at", DESCENDING)], name="idx_aianalysis_coin_generatedat"
        )
        await db[CollectionName.AI_ANALYSIS.value].create_index(
            [("prompt_version", ASCENDING), ("model", ASCENDING), ("generated_at", DESCENDING)],
            name="idx_aianalysis_prompt_model_generatedat",
        )

        logger.info("Database indexes initialized.")
    except PyMongoError as exc:
        logger.warning("Index initialization skipped/incomplete: %s", exc.__class__.__name__)
