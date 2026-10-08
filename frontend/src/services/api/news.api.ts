import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type {
  CoinSentimentResponse,
  NewsListResponse,
  NewsQuery,
  NewsSourcesResponse,
  SentimentTimeframe,
} from "../../types/news";

/** Query params shared by the global and coin-scoped feeds. Filtering happens on the backend. */
function toParams(query: NewsQuery) {
  return {
    page: query.page,
    limit: query.limit,
    search: query.search || undefined,
    source: query.source || undefined,
    sentiment: query.sentiment,
    date_from: query.dateFrom,
    date_to: query.dateTo,
  };
}

/**
 * Latest news, newest first. With `coinId` it uses the coin-scoped endpoint
 * (relevance decided by the backend's coin association); otherwise the
 * global feed. `coinId` on the global feed is not used — see coin endpoint.
 */
export async function fetchNews(query: NewsQuery = {}, signal?: AbortSignal): Promise<NewsListResponse> {
  const url = query.coinId ? apiConfig.endpoints.coinNews(query.coinId) : apiConfig.endpoints.news;
  const { data } = await apiClient.get<NewsListResponse>(url, { params: toParams(query), signal });
  return data;
}

export async function fetchNewsSources(signal?: AbortSignal): Promise<NewsSourcesResponse> {
  const { data } = await apiClient.get<NewsSourcesResponse>(apiConfig.endpoints.newsSources, { signal });
  return data;
}

export async function fetchCoinSentiment(
  coinId: string,
  timeframe: SentimentTimeframe,
  signal?: AbortSignal
): Promise<CoinSentimentResponse> {
  const { data } = await apiClient.get<CoinSentimentResponse>(apiConfig.endpoints.coinSentiment(coinId), {
    params: { timeframe },
    signal,
  });
  return data;
}
