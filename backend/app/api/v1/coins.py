"""Coin endpoints — listing, search, detail. All business logic lives in CoinService."""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Query

from app.schemas.coin import Coin, CoinListResponse, CoinSearchResponse
from app.providers.timeframes import Timeframe
from app.schemas.market import HistoricalPriceResponse, MarketData
from app.schemas.fundamentals import FundamentalAnalysisResponse
from app.schemas.news import NewsListResponse
from app.schemas.sentiment import CoinSentimentResponse, SentimentTimeframe
from app.schemas.technical_analysis import TechnicalAnalysisResponse
from app.services.coin_service import CoinService
from app.services.fundamental_analysis_service import FundamentalAnalysisService
from app.services.market_service import MarketService
from app.services.news_service import MAX_NEWS_LIMIT, NewsService
from app.services.sentiment_service import SentimentService
from app.services.technical_analysis_service import TechnicalAnalysisService

router = APIRouter(prefix="/coins", tags=["Coins"])


def _service() -> CoinService:
    return CoinService()


@router.get("/search", response_model=CoinSearchResponse)
async def search_coins(
    q: str = Query(..., min_length=1, max_length=100, description="Search text"),
    limit: int = Query(20, ge=1, le=100),
) -> CoinSearchResponse:
    """
    Case-insensitive search over name/symbol/slug against the
    normalized MongoDB coin collection — never calls a provider
    per-request.
    """
    return await _service().search_coins(q, limit=limit)


@router.get("", response_model=CoinListResponse)
async def list_coins(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=250),
    active_only: bool = Query(True),
    provider: Optional[str] = Query(None, description="'coingecko' or 'binance'"),
    sort_by: str = Query("market_cap_rank"),
    sort_direction: str = Query("asc", pattern="^(asc|desc)$"),
) -> CoinListResponse:
    """Paginated coin listing — the full synchronized coin universe, not a fixed top-N."""
    return await _service().list_coins(
        page, limit,
        active_only=active_only,
        provider=provider,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )


@router.get("/{coin_id}", response_model=Coin)
async def get_coin(coin_id: str) -> Coin:
    """Fetch a coin by its internal canonical ID (never a raw provider ID)."""
    return await _service().get_coin(coin_id)


@router.get("/{coin_id}/market", response_model=MarketData)
async def get_coin_market(coin_id: str) -> MarketData:
    """Current market snapshot for a coin, by its internal canonical ID."""
    return await MarketService().get_coin_market_data(coin_id)


@router.get("/{coin_id}/history", response_model=HistoricalPriceResponse)
async def get_coin_history(
    coin_id: str,
    timeframe: Timeframe = Query(Timeframe.DAY_7, description="Historical range"),
) -> HistoricalPriceResponse:
    """
    Historical OHLC candles for a coin, by its internal canonical ID.

    FastAPI validates `timeframe` against the Timeframe enum, so an
    unsupported value returns a 422 listing the accepted options
    rather than being silently coerced. See
    app/providers/timeframes.py for why sub-daily ranges (1H/4H) are
    not offered.
    """
    return await MarketService().get_coin_history(coin_id, timeframe)


@router.get("/{coin_id}/technical-analysis", response_model=TechnicalAnalysisResponse)
async def get_coin_technical_analysis(
    coin_id: str,
    timeframe: Timeframe = Query(Timeframe.DAY_30, description="Historical range the indicators are computed over"),
    force_refresh: bool = Query(False, description="Bypass the cached snapshot and recompute now"),
) -> TechnicalAnalysisResponse:
    """
    RSI, MACD, moving averages, Bollinger Bands, ATR, volume,
    support/resistance, and a descriptive trend label for a coin, by
    its internal canonical ID — computed from real historical OHLC
    candles (see app/services/technical_analysis_service.py).

    A `1D` timeframe's ~30-minute candles give too few daily-scale
    data points for indicators like SMA 200; `30D` is the default so
    the Coin Details page gets a meaningful result without the caller
    needing to know that up front. Any supported Timeframe can still
    be requested explicitly.
    """
    return await TechnicalAnalysisService().get_technical_analysis(coin_id, timeframe, force_refresh=force_refresh)


@router.get("/{coin_id}/fundamentals", response_model=FundamentalAnalysisResponse)
async def get_coin_fundamentals(
    coin_id: str,
    force_refresh: bool = Query(
        False, description="Re-fetch provider project data now (rate-limited per coin)"
    ),
) -> FundamentalAnalysisResponse:
    """
    Fundamental analysis for a coin, by its internal canonical ID:
    provider-reported market/supply/valuation/project/ecosystem data,
    clearly separated calculated metrics, a rule-based fundamental score
    and a factual summary (see app/services/fundamental_analysis_service.py
    and docs/fundamental-analysis.md).

    Sections the provider can't supply come back null and are listed in
    `unavailable_sections` — nothing is estimated or substituted.
    """
    return await FundamentalAnalysisService().get_fundamentals(coin_id, force_refresh=force_refresh)


@router.get("/{coin_id}/news", response_model=NewsListResponse)
async def get_coin_news(
    coin_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=MAX_NEWS_LIMIT),
    search: Optional[str] = Query(None, max_length=100),
    source: Optional[str] = Query(None, max_length=100),
    sentiment: Optional[Literal["positive", "neutral", "negative"]] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
) -> NewsListResponse:
    """
    Latest news associated with a coin, by its internal canonical ID.
    Association is made at ingestion time from the provider's own coin
    tags (see app/services/news_coin_matcher.py), not by searching text here.
    """
    return await NewsService().list_news(
        page=page, limit=limit, coin_id=coin_id, search=search, source=source,
        sentiment=sentiment, date_from=date_from, date_to=date_to,
    )


@router.get("/{coin_id}/sentiment", response_model=CoinSentimentResponse)
async def get_coin_sentiment(
    coin_id: str,
    timeframe: SentimentTimeframe = Query("24h", description="Analysis period: 24h or 7d"),
) -> CoinSentimentResponse:
    """
    Aggregated sentiment of recent news for a coin, calculated from real
    analyzed articles. Reports `insufficient_data` instead of a label when
    too few articles have been analyzed. Descriptive only — not a prediction.
    """
    return await SentimentService().get_coin_sentiment(coin_id, timeframe)
