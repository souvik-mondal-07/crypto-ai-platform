"""
Crypto AI Platform — Backend entrypoint.

Run with:
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from app.api.v1 import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.database import connect, disconnect, get_database, initialize_indexes
from app.schemas.health import RootResponse
from app.services.market_refresh_scheduler import get_scheduler
from app.services.news_refresh_scheduler import get_news_scheduler

settings = get_settings()

# ---------------------------------------------------------------------------
# Logging (development-friendly; never logs secrets/tokens/passwords —
# in particular, MONGODB_URI is never logged since it may contain
# embedded credentials)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO if settings.APP_ENV == "production" else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("crypto_ai_platform")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """
    Application lifecycle: connect to MongoDB and initialize indexes on
    startup, close the client cleanly on shutdown.

    A failed MongoDB connection does NOT prevent the application from
    starting — it's logged clearly and the health endpoint will report
    "degraded"/"disconnected" until MongoDB becomes reachable. This
    matches Step 2's "fail gracefully, never silently claim connected"
    requirement, while still letting the API itself come up (useful in
    local development before MongoDB is running).
    """
    logger.info("%s starting up in '%s' mode", settings.APP_NAME, settings.APP_ENV)

    if settings.APP_ENV == "production" and settings.JWT_SECRET_KEY in (
        "your-secret-key-here",
        "change-me-in-production-this-is-not-a-real-secret",
    ):
        # Loud, but non-fatal here — Step 4 doesn't change startup
        # behavior on misconfiguration, it just makes the misconfiguration
        # impossible to miss in the logs. See docs/authentication.md.
        logger.error(
            "JWT_SECRET_KEY is still the placeholder value in a "
            "'production' environment. Set a real random secret before "
            "handling real users — every issued token is forgeable "
            "until you do."
        )

    try:
        await connect()
        await initialize_indexes(get_database())
    except PyMongoError:
        logger.error(
            "MongoDB connection failed. Is MongoDB running at the "
            "configured MONGODB_URI? See docs/development.md for how "
            "to start it locally. The API will still start, but "
            "/api/v1/health will report the database as disconnected."
        )
    except RuntimeError:
        # get_database() raising because connect() didn't establish a client
        pass

    # Background market-data refresh (Parts 2-3). Started only once per
    # process, after the DB connection attempt above; disabled entirely
    # via MARKET_REFRESH_ENABLED=false. A failed initial DB connection
    # doesn't block this from starting — individual refresh cycles will
    # simply fail (and log) until MongoDB becomes reachable, same as any
    # other DB-backed request.
    scheduler = get_scheduler()
    scheduler.start()

    # Background news ingestion + sentiment analysis (Phase 12); disabled via
    # NEWS_REFRESH_ENABLED=false. A failing provider/model never blocks startup.
    news_scheduler = get_news_scheduler()
    news_scheduler.start()

    yield

    await news_scheduler.stop()
    await scheduler.stop()
    await disconnect()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered cryptocurrency market analysis and decision-support platform.",
    lifespan=lifespan,
)

# CORS: restricted to the configured frontend origin only (never "*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", response_model=RootResponse, tags=["Root"])
async def read_root() -> RootResponse:
    """Basic API information response."""
    return RootResponse(message=f"{settings.APP_NAME} API", version=settings.APP_VERSION)
