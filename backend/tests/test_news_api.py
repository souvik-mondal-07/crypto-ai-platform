"""HTTP-level tests for /news and /coins/{id}/news|sentiment (service layer mocked, like test_coins_api)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.schemas.news import NewsFeedStatus, NewsListResponse
from app.schemas.sentiment import CoinSentimentResponse, SentimentTrend

COIN = "aaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def empty_list(**kw):
    return NewsListResponse(items=[], page=1, limit=20, total=0, pages=0, status=NewsFeedStatus(), **kw)


def test_list_news_ok_and_passes_filters(client):
    with patch("app.api.v1.news.NewsService") as cls:
        cls.return_value.list_news = AsyncMock(return_value=empty_list())
        r = client.get("/api/v1/news?page=2&limit=10&coin_id=" + COIN + "&search=etf&source=Pub&sentiment=negative&date_from=2026-09-01T00:00:00Z")
    assert r.status_code == 200 and r.json()["items"] == []
    kwargs = cls.return_value.list_news.await_args.kwargs
    assert kwargs["page"] == 2 and kwargs["limit"] == 10 and kwargs["coin_id"] == COIN
    assert kwargs["sentiment"] == "negative" and kwargs["date_from"] == datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "query", ["limit=51", "limit=0", "page=0", "sentiment=bullish", "date_from=not-a-date", "search=" + "x" * 101]
)
def test_list_news_rejects_invalid_parameters(client, query):
    assert client.get(f"/api/v1/news?{query}").status_code == 422


def test_sources_route_is_not_swallowed_by_news_id_route(client):
    with patch("app.api.v1.news.NewsService") as cls:
        from app.schemas.news import NewsSourcesResponse

        cls.return_value.list_sources = AsyncMock(return_value=NewsSourcesResponse(items=["A"]))
        r = client.get("/api/v1/news/sources")
    assert r.status_code == 200 and r.json() == {"items": ["A"]}


def test_get_news_not_found_uses_the_standard_error_shape(client):
    with patch("app.api.v1.news.NewsService") as cls:
        cls.return_value.get_news = AsyncMock(side_effect=AppError(404, "NEWS_NOT_FOUND", "No news article found."))
        r = client.get("/api/v1/news/cryptocompare:1")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NEWS_NOT_FOUND" and "Traceback" not in r.text


def test_coin_news_invalid_coin_error_shape(client):
    with patch("app.api.v1.coins.NewsService") as cls:
        cls.return_value.list_news = AsyncMock(side_effect=AppError(400, "INVALID_COIN_ID", "bad"))
        r = client.get("/api/v1/coins/xyz/news")
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_COIN_ID"


def test_coin_news_passes_coin_id_and_default_limit(client):
    with patch("app.api.v1.coins.NewsService") as cls:
        cls.return_value.list_news = AsyncMock(return_value=empty_list())
        assert client.get(f"/api/v1/coins/{COIN}/news").status_code == 200
    kwargs = cls.return_value.list_news.await_args.kwargs
    assert kwargs["coin_id"] == COIN and kwargs["limit"] == 10 and kwargs["page"] == 1


def test_news_provider_failure_does_not_become_a_500_for_reads(client):
    with patch("app.api.v1.news.NewsService") as cls:
        cls.return_value.list_news = AsyncMock(side_effect=AppError(503, "DATABASE_UNAVAILABLE", "down"))
        r = client.get("/api/v1/news")
    assert r.status_code == 503 and r.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def sentiment_payload(**kw):
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)
    base = dict(
        coin_id=COIN, timeframe="24h", status="insufficient_data", positive_count=0, neutral_count=0,
        negative_count=0, total_articles=0, trend=SentimentTrend(direction="insufficient_data"),
        min_articles_required=3, model_status="unavailable", period_start=now, period_end=now, calculated_at=now,
    )
    base.update(kw)
    return CoinSentimentResponse(**base)


def test_sentiment_endpoint_defaults_and_response_shape(client):
    with patch("app.api.v1.coins.SentimentService") as cls:
        cls.return_value.get_coin_sentiment = AsyncMock(return_value=sentiment_payload())
        r = client.get(f"/api/v1/coins/{COIN}/sentiment")
    body = r.json()
    assert r.status_code == 200 and cls.return_value.get_coin_sentiment.await_args.args == (COIN, "24h")
    assert body["status"] == "insufficient_data" and body["sentiment_label"] is None and body["average_score"] is None
    assert "not a price prediction" in body["disclaimer"]
    for key in ("positive_count", "neutral_count", "negative_count", "total_articles", "calculated_at", "timeframe"):
        assert key in body


def test_sentiment_timeframe_is_validated(client):
    assert client.get(f"/api/v1/coins/{COIN}/sentiment?timeframe=1y").status_code == 422
    with patch("app.api.v1.coins.SentimentService") as cls:
        cls.return_value.get_coin_sentiment = AsyncMock(return_value=sentiment_payload(timeframe="7d"))
        assert client.get(f"/api/v1/coins/{COIN}/sentiment?timeframe=7d").status_code == 200


def test_sentiment_unknown_coin_is_404(client):
    with patch("app.api.v1.coins.SentimentService") as cls:
        cls.return_value.get_coin_sentiment = AsyncMock(side_effect=AppError(404, "COIN_NOT_FOUND", "no"))
        assert client.get(f"/api/v1/coins/{COIN}/sentiment").status_code == 404
