/**
 * Test-only builders for news/sentiment responses. Fixtures for the test
 * suite — the application never imports this file. All text is synthetic.
 */
import type { CoinSentimentResponse, NewsArticle, NewsFeedStatus, NewsListResponse } from "../types/news";

export function buildArticle(overrides: Partial<NewsArticle> = {}): NewsArticle {
  return {
    news_id: "cryptocompare:1",
    title: "Test headline one",
    description: "Test summary one.",
    source: "Example Publisher",
    source_url: "https://publisher.example/story-1",
    image_url: null,
    author: null,
    published_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    fetched_at: new Date().toISOString(),
    provider: "cryptocompare",
    language: "en",
    categories: [],
    tags: [],
    related_coins: [],
    sentiment: null,
    ...overrides,
  };
}

export function buildStatus(overrides: Partial<NewsFeedStatus> = {}): NewsFeedStatus {
  return {
    last_sync_attempt_at: null,
    last_sync_success_at: null,
    last_sync_error_code: null,
    background_refresh_enabled: true,
    sentiment_model_status: "ready",
    ...overrides,
  };
}

export function buildNewsList(items: NewsArticle[] = [buildArticle()], overrides: Partial<NewsListResponse> = {}): NewsListResponse {
  return { items, page: 1, limit: 20, total: items.length, pages: items.length ? 1 : 0, status: buildStatus(), ...overrides };
}

export function buildSentiment(overrides: Partial<CoinSentimentResponse> = {}): CoinSentimentResponse {
  return {
    coin_id: "507f1f77bcf86cd799439011",
    timeframe: "24h",
    status: "ok",
    positive_count: 6,
    neutral_count: 3,
    negative_count: 1,
    total_articles: 10,
    positive_percent: 60,
    neutral_percent: 30,
    negative_percent: 10,
    average_score: 0.42,
    sentiment_label: "positive",
    trend: { direction: "improving", previous_average_score: 0.1, change: 0.32, previous_total_articles: 8 },
    series: [
      { bucket_start: "2026-10-01T12:00:00Z", article_count: 2, average_score: 0.3 },
      { bucket_start: "2026-10-01T16:00:00Z", article_count: 0, average_score: null },
      { bucket_start: "2026-10-01T20:00:00Z", article_count: 3, average_score: -0.2 },
    ],
    pending_article_count: 0,
    min_articles_required: 3,
    model_status: "ready",
    period_start: "2026-10-01T12:00:00Z",
    period_end: "2026-10-02T12:00:00Z",
    calculated_at: new Date().toISOString(),
    disclaimer: "Descriptive summary of the tone of recent news coverage. It is not a price prediction, trading signal or investment advice.",
    ...overrides,
  };
}

export function buildInsufficientSentiment(overrides: Partial<CoinSentimentResponse> = {}): CoinSentimentResponse {
  return buildSentiment({
    status: "insufficient_data",
    positive_count: 0,
    neutral_count: 0,
    negative_count: 0,
    total_articles: 0,
    positive_percent: null,
    neutral_percent: null,
    negative_percent: null,
    average_score: null,
    sentiment_label: null,
    trend: { direction: "insufficient_data", previous_average_score: null, change: null, previous_total_articles: 0 },
    series: [],
    ...overrides,
  });
}
