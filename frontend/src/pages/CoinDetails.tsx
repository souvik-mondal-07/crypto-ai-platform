import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ChevronRight, Star } from "lucide-react";

import { AppShell } from "../components/layout/AppShell";
import { CoinLogo } from "../components/market/CoinLogo";
import { Loader } from "../components/common/Loader";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { EmptyState } from "../components/common/EmptyState";
import { CandlestickChart } from "../components/coin-details/CandlestickChart";
import { CoinSectionNav } from "../components/coin-details/CoinSectionNav";
import { TimeframeSelector } from "../components/coin-details/TimeframeSelector";
import { CoinAthAtl, CoinMarketStats, CoinPricePerformance } from "../components/coin-details/CoinStats";
import { CoinNewsSection } from "../components/coin-details/CoinNewsSection";
import { CoinSentimentSection } from "../components/coin-details/CoinSentimentSection";
import { PredictionSection } from "../components/coin-details/PredictionSection";
import { RiskDecisionSection } from "../components/coin-details/RiskDecisionSection";
import { AiAnalysisSection } from "../components/coin-details/AiAnalysisSection";
import { FundamentalAnalysisSection } from "../components/coin-details/FundamentalAnalysisSection";
import { TechnicalAnalysisSection } from "../components/coin-details/TechnicalAnalysisSection";
import { useUserListsStore } from "../store/userListsStore";
import { useCoinDetails } from "../hooks/useCoinDetails";
import { useFundamentals } from "../hooks/useFundamentals";
import { useTechnicalAnalysis } from "../hooks/useTechnicalAnalysis";
import {
  changeColorClass,
  formatAbsoluteDateTime,
  formatPercent,
  formatRelativeTime,
  formatUsd,
} from "../utils/formatters";

export function CoinDetails() {
  const { coinId } = useParams<{ coinId: string }>();
  const navigate = useNavigate();
  const recordView = useUserListsStore((state) => state.recordView);
  const toggleWatchlist = useUserListsStore((state) => state.toggleWatchlist);
  const starred = useUserListsStore((state) => (coinId ? state.watchlist.includes(coinId) : false));

  const {
    coin,
    market,
    loading,
    error,
    notFound,
    refetch,
    timeframe,
    setTimeframe,
    candles,
    granularity,
    historyLoading,
    historyError,
    refetchHistory,
  } = useCoinDetails(coinId);

  const [showMovingAverageOverlay, setShowMovingAverageOverlay] = useState(false);
  const {
    technicalAnalysis,
    loading: technicalAnalysisLoading,
    error: technicalAnalysisError,
    insufficientData: technicalAnalysisInsufficientData,
    refetch: refetchTechnicalAnalysis,
  } = useTechnicalAnalysis(coin ? coinId : undefined, timeframe);
  // Fundamentals load independently (own loading/error/empty state), and
  // are not tied to the chart timeframe.
  const {
    fundamentals,
    loading: fundamentalsLoading,
    refreshing: fundamentalsRefreshing,
    error: fundamentalsError,
    notAvailable: fundamentalsNotAvailable,
    refetch: refetchFundamentals,
    refresh: refreshFundamentals,
  } = useFundamentals(coin ? coinId : undefined);

  // Remember this coin for the Dashboard's "Recently Viewed" (device-local).
  // This is a hook, so it must run on EVERY render, before the early returns below (a different
  // number of hooks between renders — e.g. loading -> not-found — makes React throw). It depends
  // only on primitive values, so it records once per coin load rather than on every poll/refresh.
  const viewedName = coin?.name;
  const viewedSymbol = coin?.symbol;
  const viewedLogo = coin?.logo_url ?? null;
  useEffect(() => {
    if (coinId && viewedName !== undefined && viewedSymbol !== undefined) {
      recordView({ coin_id: coinId, name: viewedName, symbol: viewedSymbol, logo_url: viewedLogo });
    }
  }, [coinId, viewedName, viewedSymbol, viewedLogo, recordView]);

  // Guard against an undefined/blank route param before anything is requested.
  if (!coinId) {
    return (
      <AppShell>
        <EmptyState message="No cryptocurrency was specified." />
        <div className="mt-4 text-center">
          <Link to="/markets" className="text-sm font-medium text-sky-600 hover:underline dark:text-sky-400">
            Back to Markets
          </Link>
        </div>
      </AppShell>
    );
  }

  if (notFound) {
    return (
      <AppShell>
        <div className="py-12 text-center">
          <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Cryptocurrency not found.</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            This coin doesn't exist, or hasn't been synchronized yet.
          </p>
          <Link
            to="/markets"
            className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 dark:bg-sky-600 dark:hover:bg-sky-500"
          >
            Back to Markets
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400">
        <Link to="/markets" className="hover:text-slate-700 hover:underline dark:hover:text-slate-200">
          Markets
        </Link>
        <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="text-slate-700 dark:text-slate-200">{coin?.name ?? "Loading..."}</span>
      </nav>

      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mb-4 flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back
      </button>

      {loading && <Loader label="Loading cryptocurrency..." />}

      {!loading && error && !notFound && (
        <div>
          <ErrorMessage message={error} />
          <button
            type="button"
            onClick={refetch}
            className="mt-2 text-sm font-medium text-sky-600 hover:underline dark:text-sky-400"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && coin && (
        <>
          {/* Coin header */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <CoinLogo src={coin.logo_url} alt={coin.name} size={44} />
              <div>
                <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                  {coin.name}{" "}
                  <span className="text-base font-medium text-slate-400">{coin.symbol}</span>
                </h1>
                {coin.market_cap_rank !== null && (
                  <p className="text-sm text-slate-400">#{coin.market_cap_rank}</p>
                )}
              </div>
              {coinId && (
                <button
                  type="button"
                  onClick={() => toggleWatchlist(coinId)}
                  aria-pressed={starred}
                  aria-label={starred ? `Remove ${coin.name} from watchlist` : `Add ${coin.name} to watchlist`}
                  title={starred ? "Remove from watchlist" : "Add to watchlist"}
                  className="rounded p-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                >
                  <Star className={`h-5 w-5 ${starred ? "fill-amber-400 text-amber-400" : "text-slate-300 hover:text-amber-400 dark:text-slate-600"}`} aria-hidden="true" />
                </button>
              )}
            </div>

            <div className="text-right">
              <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {formatUsd(market?.price_usd)}
              </p>
              <p className={`text-sm font-medium ${changeColorClass(market?.percent_change_24h)}`}>
                {market?.price_change_24h_usd !== null && market?.price_change_24h_usd !== undefined && (
                  <span>{formatUsd(market.price_change_24h_usd)} </span>
                )}
                ({formatPercent(market?.percent_change_24h)}) 24h
              </p>
            </div>
          </div>

          {market?.last_updated && (
            <p
              className="mt-2 text-xs text-slate-400"
              title={formatAbsoluteDateTime(market.last_updated)}
            >
              Last updated: {formatRelativeTime(market.last_updated)}
              {market.is_stale && " — this data may be out of date"}
            </p>
          )}

          {!market && (
            <p className="mt-2 text-xs text-slate-400">
              No market data has been synchronized for this coin yet.
            </p>
          )}

          <CoinSectionNav
            sections={[
              { id: "coin-overview", label: "Overview" },
              { id: "coin-chart", label: "Chart" },
              { id: "coin-technical", label: "Technical" },
              { id: "coin-fundamental", label: "Fundamental" },
              { id: "coin-sentiment", label: "Sentiment" },
              { id: "coin-prediction", label: "Prediction" },
              { id: "coin-risk-decision", label: "Risk & Decision" },
              { id: "coin-ai-analysis", label: "AI Analysis" },
              { id: "coin-news", label: "News" },
            ]}
          />

          {/* Chart */}
          <div id="coin-chart" className="mt-6 scroll-mt-28 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Price Chart</h2>
                {granularity && !historyLoading && (
                  <p className="text-xs text-slate-400">{granularity} candles</p>
                )}
              </div>
              <TimeframeSelector value={timeframe} onChange={setTimeframe} disabled={historyLoading} />
            </div>

            {historyLoading && (
              <div className="flex h-[400px] items-center justify-center">
                <Loader label="Loading chart data..." />
              </div>
            )}

            {!historyLoading && historyError && (
              <div className="flex h-[400px] flex-col items-center justify-center gap-2">
                <ErrorMessage message="Unable to load historical data." />
                <button
                  type="button"
                  onClick={refetchHistory}
                  className="text-sm font-medium text-sky-600 hover:underline dark:text-sky-400"
                >
                  Retry
                </button>
              </div>
            )}

            {!historyLoading && !historyError && candles.length === 0 && (
              <div className="flex h-[400px] items-center justify-center">
                <EmptyState message="No historical data available for this timeframe." />
              </div>
            )}

            {!historyLoading && !historyError && candles.length > 0 && (
              <CandlestickChart candles={candles} showMovingAverages={showMovingAverageOverlay} />
            )}
          </div>

          {/* Market statistics */}
          <div id="coin-overview" className="mt-6 scroll-mt-28">
            <CoinMarketStats coin={coin} market={market} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <CoinPricePerformance market={market} />
            <CoinAthAtl market={market} />
          </div>

          <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-4 text-center dark:border-slate-700">
            <p className="text-xs text-slate-400">AI-assisted analysis is not implemented yet.</p>
          </div>

          <div id="coin-technical" className="scroll-mt-28">
          <TechnicalAnalysisSection
            technicalAnalysis={technicalAnalysis}
            loading={technicalAnalysisLoading}
            error={technicalAnalysisError}
            insufficientData={technicalAnalysisInsufficientData}
            onRetry={refetchTechnicalAnalysis}
            showMovingAverageOverlay={showMovingAverageOverlay}
            onToggleMovingAverageOverlay={setShowMovingAverageOverlay}
          />
          </div>

          <div id="coin-fundamental" className="scroll-mt-28">
          <FundamentalAnalysisSection
            fundamentals={fundamentals}
            loading={fundamentalsLoading}
            refreshing={fundamentalsRefreshing}
            error={fundamentalsError}
            notAvailable={fundamentalsNotAvailable}
            onRetry={refetchFundamentals}
            onRefresh={refreshFundamentals}
          />
          </div>

          {/* Phase 12: news + sentiment load independently (own loading/error/empty states). */}
          <div id="coin-sentiment" className="scroll-mt-28">
            <CoinSentimentSection key={`sentiment-${coinId}`} coinId={coinId} />
          </div>
          {/* Phase 13: ML prediction loads independently (own loading/error/unavailable states). */}
          <div id="coin-prediction" className="scroll-mt-28">
            <PredictionSection key={`prediction-${coinId}`} coinId={coinId} />
          </div>
          {/* Phase 14: risk & decision loads independently (own loading/error/no-decision states). */}
          <div id="coin-risk-decision" className="scroll-mt-28">
            <RiskDecisionSection key={`risk-decision-${coinId}`} coinId={coinId} />
          </div>
          {/* Phase 15: Gemini explains the analysis above. Loads independently; failure never affects the page. */}
          <div id="coin-ai-analysis" className="scroll-mt-28">
            <AiAnalysisSection key={`ai-analysis-${coinId}`} coinId={coinId} />
          </div>
          <div id="coin-news" className="scroll-mt-28">
            <CoinNewsSection key={`news-${coinId}`} coinId={coinId} coinName={coin.name} />
          </div>
        </>
      )}
    </AppShell>
  );
}
