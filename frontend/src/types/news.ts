/** Mirrors backend/app/schemas/news.py and sentiment.py (Phase 12). */

export type SentimentLabel = "positive" | "neutral" | "negative";
export type SentimentTimeframe = "24h" | "7d";

export interface ArticleSentiment {
  label: SentimentLabel;
  /** P(positive) − P(negative), in [-1, 1]. */
  score: number;
  confidence: number;
  probabilities: Record<string, number>;
  model: string;
  analyzed_at: string;
}

export interface RelatedCoin {
  coin_id: string;
  symbol: string;
  name: string | null;
  logo_url: string | null;
}

export interface NewsArticle {
  news_id: string;
  title: string;
  description: string | null;
  source: string;
  /** The original article at the publisher. */
  source_url: string;
  image_url: string | null;
  author: string | null;
  published_at: string;
  fetched_at: string;
  provider: string;
  language: string | null;
  categories: string[];
  tags: string[];
  related_coins: RelatedCoin[];
  /** Null until the article has been analyzed. */
  sentiment: ArticleSentiment | null;
}

export type SentimentModelStatus = "disabled" | "not_loaded" | "ready" | "unavailable";

export interface NewsFeedStatus {
  last_sync_attempt_at: string | null;
  last_sync_success_at: string | null;
  last_sync_error_code: string | null;
  background_refresh_enabled: boolean;
  sentiment_model_status: SentimentModelStatus;
}

export interface NewsListResponse {
  items: NewsArticle[];
  page: number;
  limit: number;
  total: number;
  pages: number;
  status: NewsFeedStatus;
}

export interface NewsSourcesResponse {
  items: string[];
}

export interface NewsQuery {
  page?: number;
  limit?: number;
  search?: string;
  source?: string;
  sentiment?: SentimentLabel;
  /** ISO 8601 */
  dateFrom?: string;
  dateTo?: string;
  /** Internal coin id — selects the coin-scoped endpoint. */
  coinId?: string;
}

export type SentimentTrendDirection = "improving" | "declining" | "stable" | "insufficient_data";

export interface SentimentBucket {
  bucket_start: string;
  article_count: number;
  average_score: number | null;
}

export interface CoinSentimentResponse {
  coin_id: string;
  timeframe: SentimentTimeframe;
  status: "ok" | "insufficient_data";
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  total_articles: number;
  positive_percent: number | null;
  neutral_percent: number | null;
  negative_percent: number | null;
  average_score: number | null;
  sentiment_label: SentimentLabel | null;
  trend: {
    direction: SentimentTrendDirection;
    previous_average_score: number | null;
    change: number | null;
    previous_total_articles: number;
  };
  series: SentimentBucket[];
  pending_article_count: number;
  min_articles_required: number;
  model_status: SentimentModelStatus;
  period_start: string;
  period_end: string;
  calculated_at: string;
  disclaimer: string;
}
