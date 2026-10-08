"""
Development-only market synchronization trigger.

*** NOT a public admin API. ***

This endpoint only exists when `ENABLE_DEV_SYNC_ENDPOINT=true` is set
in the environment (default: false — see `backend/.env.example`). When
disabled, the route is never registered on the FastAPI app at all
(see `app/api/v1/__init__.py`), so it 404s rather than merely being
"hidden". This is a development convenience, not an authentication
mechanism — Step 3 explicitly does not implement auth. Do not enable
this in any publicly reachable deployment. Production/scheduled
synchronization (Celery, etc.) is a future step.
"""

from fastapi import APIRouter, Query

from app.services.market_sync_service import (
    DEFAULT_MAX_MARKET_PAGES,
    DEFAULT_PER_PAGE,
    MarketSyncService,
)

router = APIRouter(prefix="/dev/sync", tags=["Dev — Sync (development only)"])


@router.post("/market")
async def trigger_market_sync(
    # `le=100` (25,000 coins at the max per_page) is deliberately high
    # enough to cover the entire ~21k-coin ranked universe in a single
    # manual call for one-off validation/backfill (Part 20) — the
    # background scheduler (see market_refresh_scheduler.py) is what
    # actually keeps data fresh day to day, at a much smaller
    # per-cycle page budget (MARKET_REFRESH_MAX_PAGES).
    max_pages: int = Query(DEFAULT_MAX_MARKET_PAGES, ge=1, le=100),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=250),
    include_full_universe: bool = Query(True),
    include_binance_mapping: bool = Query(True),
) -> dict:
    """
    Manually trigger a CoinGecko (+ optional Binance mapping) sync.
    Development use only — see module docstring.
    """
    service = MarketSyncService()
    result = await service.sync(
        max_market_pages=max_pages,
        per_page=per_page,
        include_full_universe=include_full_universe,
        include_binance_mapping=include_binance_mapping,
    )
    return {
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "duration_seconds": round(result.duration_seconds, 2),
        "full_universe_count": result.full_universe_count,
        "coins_matched": result.coins_matched,
        "coins_upserted": result.coins_upserted,
        "market_data_matched": result.market_data_matched,
        "market_data_upserted": result.market_data_upserted,
        "market_pages_fetched": result.market_pages_fetched,
        "binance_pairs_mapped": result.binance_pairs_mapped,
        "errors": result.errors,
    }


@router.post("/news")
async def trigger_news_sync(
    max_pages: int = Query(3, ge=1, le=10),
    analyze_sentiment: bool = Query(True),
) -> dict:
    """Manually run one news ingestion (+ sentiment) pass. Development use only."""
    from app.services.news_ingestion_service import NewsIngestionService
    from app.services.sentiment_analysis_service import SentimentAnalysisService

    sync = await NewsIngestionService().sync_latest(max_pages=max_pages)
    analysis = await SentimentAnalysisService().analyze_pending() if analyze_sentiment else None
    return {
        "pages_fetched": sync.pages_fetched,
        "articles_seen": sync.articles_seen,
        "inserted": sync.inserted,
        "already_stored": sync.already_stored,
        "malformed_dropped": sync.malformed_dropped,
        "associated_with_coins": sync.associated_with_coins,
        "errors": sync.errors,
        "sentiment": None if analysis is None else {
            "analyzed": analysis.analyzed,
            "failed": analysis.failed,
            "model_status": analysis.model_status,
            "error": analysis.error,
        },
    }
