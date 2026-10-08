import { env } from "./environment";

/**
 * Centralized API configuration. New endpoints should be added here as
 * they're introduced, rather than being hard-coded inside services.
 */
export const apiConfig = {
  baseURL: env.apiBaseUrl,
  timeout: 10_000,
  /** Generating an AI explanation calls an LLM and can take far longer than a normal request. */
  aiGenerationTimeout: 60_000,
  endpoints: {
    health: "/health",
    authRegister: "/auth/register",
    authLogin: "/auth/login",
    authMe: "/auth/me",
    authLogout: "/auth/logout",
    coins: "/coins",
    coinsSearch: "/coins/search",
    coinById: (coinId: string) => `/coins/${coinId}`,
    coinMarket: (coinId: string) => `/coins/${coinId}/market`,
    coinHistory: (coinId: string) => `/coins/${coinId}/history`,
    coinTechnicalAnalysis: (coinId: string) => `/coins/${coinId}/technical-analysis`,
    coinFundamentals: (coinId: string) => `/coins/${coinId}/fundamentals`,
    coinNews: (coinId: string) => `/coins/${coinId}/news`,
    coinSentiment: (coinId: string) => `/coins/${coinId}/sentiment`,
    coinPredictions: (coinId: string) => `/predictions/${coinId}`,
    coinDecision: (coinId: string) => `/decisions/${coinId}`,
    coinAiAnalysis: (coinId: string) => `/ai-analysis/${coinId}`,
    coinAiAnalysisGenerate: (coinId: string) => `/ai-analysis/${coinId}/generate`,
    news: "/news",
    newsSources: "/news/sources",
    marketOverview: "/market/overview",
    marketGainers: "/market/gainers",
    marketLosers: "/market/losers",
    marketGlobal: "/market/global",
    marketTrending: "/market/trending",
    marketCoins: "/market/coins",
    marketTopMarketCap: "/market/top/market-cap",
    marketTopVolume: "/market/top/volume",
    marketBinanceTickers: "/market/exchange/binance/tickers",
  },
} as const;
