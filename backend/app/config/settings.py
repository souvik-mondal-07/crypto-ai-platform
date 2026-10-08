"""
Centralized application configuration.

All environment-driven values must be read through this module.
Do not read os.environ directly anywhere else in the backend.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # General
    APP_NAME: str = "Crypto AI Platform"
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Server
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000

    # CORS / Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # MongoDB
    # Credentials, if any, belong in MONGODB_URI itself
    # (mongodb://user:pass@host:port) — never as separate plain fields.
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "crypto_ai_platform"

    # Market data providers (Step 3)
    COINGECKO_API_BASE_URL: str = "https://api.coingecko.com/api/v3"
    # Optional — CoinGecko's public endpoints used here do not require
    # a key. If set, it's sent as the x-cg-demo-api-key header (free
    # tier) to raise the provider's own rate limit. Never required to
    # run Step 3.
    COINGECKO_API_KEY: str = ""
    BINANCE_API_BASE_URL: str = "https://api.binance.com"

    # --- Real-time market-data background refresh ---
    # A lightweight asyncio background loop (started/stopped from
    # app/main.py's lifespan) that keeps `market_data` fresh without
    # requiring a manual /dev/sync call or a backend restart. See
    # app/services/market_refresh_scheduler.py and docs/market-data.md.

    # Master on/off switch. Disabling this does NOT disable the
    # dev-only manual sync endpoint — that remains independently
    # gated by ENABLE_DEV_SYNC_ENDPOINT.
    MARKET_REFRESH_ENABLED: bool = True

    # How often the background loop wakes up to run one refresh cycle.
    MARKET_REFRESH_INTERVAL_SECONDS: int = 60

    # Total CoinGecko /coins/markets pages fetched per cycle. Split
    # between MARKET_REFRESH_HOT_PAGES (refreshed every cycle) and a
    # slowly-rotating "cold" window covering the rest of the ranked
    # universe (see MarketRefreshScheduler) so pages beyond the old
    # hardcoded cap of 4 are no longer permanently stale.
    MARKET_REFRESH_MAX_PAGES: int = 8
    # The highest-ranked N pages (by market cap) — the coins the
    # Dashboard/Markets overview, gainers and losers actually read —
    # refreshed on every single cycle regardless of the cold rotation.
    MARKET_REFRESH_HOT_PAGES: int = 2
    MARKET_REFRESH_PER_PAGE: int = 250
    # Delay between successive CoinGecko page requests within one
    # cycle — spaces out calls so a cycle doesn't burst-fire
    # MARKET_REFRESH_MAX_PAGES requests back to back.
    MARKET_REFRESH_REQUEST_DELAY_SECONDS: float = 1.5

    # Whether each cycle also refreshes Binance-mapped coins' live
    # price/24h fields from Binance's 24hr ticker (one bulk call covers
    # every mapped coin — this is the "near-real-time" path for
    # Binance-listed assets; CoinGecko pagination above is the fallback
    # path for everything else, per docs/market-data.md).
    MARKET_REFRESH_INCLUDE_BINANCE: bool = True

    # How often (separately from the fast cycle above) the full
    # CoinGecko coin-universe listing and Binance trading-pair mapping
    # are re-synced, to pick up newly listed/delisted coins. This is
    # deliberately much less frequent than the price refresh — it's a
    # broad catalog resync, not a price update.
    MARKET_REFRESH_UNIVERSE_INTERVAL_SECONDS: int = 21600  # 6 hours

    # Fundamental analysis (Phase 11). Project/ecosystem data (description,
    # links, developer activity) changes slowly, so a fetched profile is
    # reused for this long before the provider is asked again. Market-derived
    # metrics are NOT cached this way — they are recalculated from the live
    # market_data snapshot on every request.
    FUNDAMENTALS_PROFILE_TTL_SECONDS: int = 21600  # 6 hours

    # Floor between provider fetches for one coin even when the client asks
    # for force_refresh, so the refresh button can't hammer the provider.
    FUNDAMENTALS_MIN_REFRESH_INTERVAL_SECONDS: int = 60

    # --- News & sentiment (Phase 12) ---
    # News provider: CryptoCompare / CoinDesk Data "legacy" news endpoint
    # (public REST API, no scraping). The key is OPTIONAL for light use but
    # raises the provider's rate limit; it is read only here, server-side,
    # and is never sent to the frontend.
    CRYPTOCOMPARE_API_KEY: str = ""
    CRYPTOCOMPARE_API_BASE_URL: str = "https://min-api.cryptocompare.com"
    NEWS_LANGUAGE: str = "EN"

    # Background news ingestion (same asyncio-loop pattern as the market
    # refresh scheduler — no Redis/Celery). Compatible with a future job runner.
    NEWS_REFRESH_ENABLED: bool = True
    NEWS_REFRESH_INTERVAL_SECONDS: int = 600
    NEWS_REFRESH_INITIAL_DELAY_SECONDS: int = 10
    # Max provider pages (~50 articles each) fetched per cycle. Paging stops
    # early as soon as a page contains nothing new.
    NEWS_FETCH_MAX_PAGES: int = 3
    NEWS_FETCH_PAGE_DELAY_SECONDS: float = 1.0
    # Stored description is a short excerpt of the provider's text, not the full article.
    NEWS_DESCRIPTION_MAX_CHARS: int = 400

    # Sentiment engine. The classifier is pluggable (see
    # app/services/sentiment_model.py); "finbert" is the only backend today.
    SENTIMENT_ENABLED: bool = True
    SENTIMENT_MODEL_BACKEND: str = "finbert"
    SENTIMENT_MODEL_NAME: str = "ProsusAI/finbert"
    # Optional: where the Hugging Face model files are cached (default: HF's own cache).
    SENTIMENT_MODEL_CACHE_DIR: str = ""
    # True = never touch the network for the model (use only already-downloaded files).
    SENTIMENT_LOCAL_FILES_ONLY: bool = False
    SENTIMENT_BATCH_SIZE: int = 16
    SENTIMENT_MAX_ARTICLES_PER_CYCLE: int = 200
    SENTIMENT_MAX_TOKENS: int = 256
    # After a failed model load, wait this long before trying again.
    SENTIMENT_MODEL_RETRY_SECONDS: int = 600
    # Aggregation rules (see app/services/sentiment_aggregation.py).
    SENTIMENT_MIN_ARTICLES: int = 3
    SENTIMENT_LABEL_THRESHOLD: float = 0.15
    SENTIMENT_TREND_THRESHOLD: float = 0.10

    # --- ML prediction engine (Phase 13) ---
    # Models are trained explicitly (python -m ml.pipelines.training_pipeline) and
    # only LOADED here — nothing trains at API start-up or per request.
    # Relative paths are resolved against the repository root.
    ML_ARTIFACT_DIR: str = "ml/artifacts"
    ML_DEFAULT_HORIZON: str = "24h"
    ML_DEFAULT_MODEL: str = "xgboost"
    # Minimum real candles required to train a model for a coin/horizon.
    ML_MIN_HISTORY_LENGTH: int = 500
    # A stored prediction is served as-is for this long, then regenerated.
    ML_PREDICTION_TTL_SECONDS: int = 900

    # --- Risk & Decision engine (Phase 14) ---
    # Weights/thresholds live in app/config/risk_config.py (versioned). Only the operational
    # knob is an env setting: how long the decision waits for Phase 13 to generate a prediction
    # before falling back to the latest stored one (or marking the prediction unavailable).
    DECISION_PREDICTION_TIMEOUT_SECONDS: float = 8.0

    # --- Gemini AI analysis (Phase 15) ---
    # Gemini only EXPLAINS the structured output of the existing engines (it never decides, never
    # predicts a price). The key is read only here, server-side, and is never sent to the frontend.
    # Provider tuning lives in app/config/gemini_config.py (GeminiConfig), built from these values.
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_TIMEOUT_SECONDS: float = 30.0
    GEMINI_MAX_OUTPUT_TOKENS: int = 4096
    # Analytical, not creative: keep the temperature low.
    GEMINI_TEMPERATURE: float = 0.2
    # Extra attempts after the first for timeouts / 5xx / malformed output (never for auth or 429).
    GEMINI_MAX_RETRIES: int = 2
    GEMINI_RETRY_BACKOFF_SECONDS: float = 1.5
    # A stored AI analysis is served as-is for this long before a new one may be generated.
    AI_ANALYSIS_TTL_SECONDS: int = 1800
    # Floor between two generations for the same coin, even when the user asks to regenerate.
    AI_ANALYSIS_MIN_REGENERATE_INTERVAL_SECONDS: int = 60
    # Max Gemini requests in flight at once across the whole backend.
    AI_ANALYSIS_MAX_CONCURRENT_GENERATIONS: int = 2

    # Dev-only coin/market synchronization endpoint (see docs/market-data.md).
    # Off by default — must be explicitly enabled, and is intended for
    # local development only. This is NOT authentication; it exists
    # only so Step 3's manual sync trigger isn't a public unauthenticated
    # endpoint by default.
    ENABLE_DEV_SYNC_ENDPOINT: bool = False

    # Authentication (Step 4)
    # NEVER use this default outside local development — it is
    # intentionally an obvious placeholder so a real deployment can't
    # accidentally ship with it. See docs/authentication.md.
    JWT_SECRET_KEY: str = "change-me-in-production-this-is-not-a-real-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> List[str]:
        """
        Development CORS origins.

        Only the configured frontend URL is allowed. This is intentionally
        restrictive (never "*") and should be extended per-environment in
        later steps (e.g. staging/production URLs).
        """
        return [self.FRONTEND_URL]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (avoids re-parsing env on every call)."""
    return Settings()
