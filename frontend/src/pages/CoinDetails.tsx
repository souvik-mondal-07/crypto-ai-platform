import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Bell, ChevronRight, Wallet } from "lucide-react";

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
import { WatchlistButton } from "../components/watchlist/WatchlistButton";
import { DataKindBadge } from "../components/ui/DataKindBadge";
import { useChartHeight } from "../hooks/useChartHeight";
import { useRecordHistory } from "../hooks/useRecordHistory";
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
  const { hash } = useLocation();
  const chartHeight = useChartHeight();
  const recordView = useUserListsStore((state) => state.recordView);

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

  // Phase 16: remember (per user) that this coin's analysis was viewed, once it has really loaded.
  useRecordHistory(coin ? coinId : undefined, "coin_analysis", technicalAnalysis !== null && technicalAnalysis !== undefined);

  // Deep links from the History page (/coins/:id#coin-prediction) jump to the relevant section once the coin has loaded.
  useEffect(() => {
    if (!coin || !hash) return;
    const target = document.getElementById(hash.slice(1));
    if (target && typeof target.scrollIntoView === "function") target.scrollIntoView({ block: "start" });
  }, [coin, hash]);

  // Every hook above this point runs on every render; the early returns below must stay AFTER all hooks.
  // Remember this coin for the Dashboard's "Recently Viewed" (device-local).
  const viewedName = coin?.name;
  useEffect(() => {
    if (coin && coinId) {
      recordView({ coin_id: coinId, name: coin.name, symbol: coin.symbol, logo_url: coin.logo_url });
    }
    // Record once per coin load, not on every poll/refresh of the same coin.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coinId, viewedName]);

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
          <p className="page-subtitle">
            This coin doesn't exist, or hasn't been synchronized yet.
          </p>
          <Link
            to="/markets"
            className="btn-primary mt-4"
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
        className="btn-ghost mb-4 !px-2"
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
          {/* Coin identity + current price */}
          <div className="card card-pad">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex min-w-0 items-center gap-3">
                <CoinLogo src={coin.logo_url} alt={coin.name} size={48} />
                <div className="min-w-0">
                  <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-2xl">
                    {coin.name}{" "}
                    <span className="text-base font-medium text-slate-400">{coin.symbol}</span>
                  </h1>
                  {coin.market_cap_rank !== null && (
                    <p className="text-sm text-slate-400">#{coin.market_cap_rank}</p>
                  )}
                </div>
              </div>

              <div className="text-left sm:text-right">
                <p className="text-2xl font-bold tabular-nums tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
                  {formatUsd(market?.price_usd)}
                </p>
                <p className={`text-sm font-medium tabular-nums ${changeColorClass(market?.percent_change_24h)}`}>
                  {market?.price_change_24h_usd !== null && market?.price_change_24h_usd !== undefined && (
                    <span>{formatUsd(market.price_change_24h_usd)} </span>
                  )}
                  ({formatPercent(market?.percent_change_24h)}) 24h
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
              {coinId && <WatchlistButton coinId={coinId} coinName={coin.name} />}
              <Link
                to="/portfolio"
                state={{ addCoin: { id: coin.id, name: coin.name, symbol: coin.symbol, logo_url: coin.logo_url } }}
                className="btn-secondary"
              >
                <Wallet className="h-4 w-4" aria-hidden="true" />
                Add to Portfolio
              </Link>
              <Link
                to="/alerts"
                state={{ alertCoin: { id: coin.id, name: coin.name, symbol: coin.symbol, logo_url: coin.logo_url } }}
                className="btn-secondary"
              >
                <Bell className="h-4 w-4" aria-hidden="true" />
                Set price alert
              </Link>
              <DataKindBadge kind="observed" />
            </div>

            {market?.last_updated && (
              <p className="mt-3 text-xs text-slate-400" title={formatAbsoluteDateTime(market.last_updated)}>
                Last updated: {formatRelativeTime(market.last_updated)}
                {market.is_stale && " — this data may be out of date"}
              </p>
            )}

            {!market && (
              <p className="mt-3 text-xs text-slate-400">No market data has been synchronized for this coin yet.</p>
            )}
          </div>

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
          <div id="coin-chart" className="mt-6 scroll-mt-40 card card-pad lg:scroll-mt-28">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="section-title">Price Chart</h2>
                {granularity && !historyLoading && (
                  <p className="text-xs text-slate-400">{granularity} candles</p>
                )}
              </div>
              <TimeframeSelector value={timeframe} onChange={setTimeframe} disabled={historyLoading} />
            </div>

            {historyLoading && (
              <div className="flex h-[280px] items-center justify-center sm:h-[400px]">
                <Loader label="Loading chart data..." />
              </div>
            )}

            {!historyLoading && historyError && (
              <div className="flex h-[280px] flex-col items-center justify-center gap-2 sm:h-[400px]">
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
              <div className="flex h-[280px] items-center justify-center sm:h-[400px]">
                <EmptyState message="No historical data available for this timeframe." />
              </div>
            )}

            {!historyLoading && !historyError && candles.length > 0 && (
              <>
                <CandlestickChart candles={candles} showMovingAverages={showMovingAverageOverlay} height={chartHeight} />
                {showMovingAverageOverlay && (
                  <ul aria-label="Chart legend" className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                    <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-amber-500" aria-hidden="true" />SMA 20</li>
                    <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-violet-500" aria-hidden="true" />SMA 50</li>
                  </ul>
                )}
              </>
            )}
          </div>

          {/* Market statistics */}
          <div id="coin-overview" className="mt-6 scroll-mt-40 lg:scroll-mt-28">
            <CoinMarketStats coin={coin} market={market} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <CoinPricePerformance market={market} />
            <CoinAthAtl market={market} />
          </div>

          <p role="note" className="mt-6 rounded-lg border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            Each section below is labelled by what it is: <strong className="font-medium">observed data</strong> is measured, while
            <strong className="font-medium"> model estimates</strong>, <strong className="font-medium">risk assessments</strong> and
            <strong className="font-medium"> AI-generated</strong> text are analysis. None of it is a guarantee of future prices or financial advice.
          </p>

          <div id="coin-technical" className="scroll-mt-40 lg:scroll-mt-28">
            <div className="-mb-3 mt-6"><DataKindBadge kind="observed" /></div>
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

          <div id="coin-fundamental" className="scroll-mt-40 lg:scroll-mt-28">
            <div className="-mb-3 mt-6"><DataKindBadge kind="observed" /></div>
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
          <div id="coin-sentiment" className="scroll-mt-40 lg:scroll-mt-28">
            <div className="-mb-3 mt-6"><DataKindBadge kind="model" /></div>
            <CoinSentimentSection key={`sentiment-${coinId}`} coinId={coinId} />
          </div>
          {/* Phase 13: ML prediction loads independently (own loading/error/unavailable states). */}
          <div id="coin-prediction" className="scroll-mt-40 lg:scroll-mt-28">
            <div className="-mb-3 mt-6"><DataKindBadge kind="model" /></div>
            <PredictionSection key={`prediction-${coinId}`} coinId={coinId} />
          </div>
          {/* Phase 14: risk & decision loads independently (own loading/error/no-decision states). */}
          <div id="coin-risk-decision" className="scroll-mt-40 lg:scroll-mt-28">
            <div className="-mb-3 mt-6"><DataKindBadge kind="risk" /></div>
            <RiskDecisionSection key={`risk-decision-${coinId}`} coinId={coinId} />
          </div>
          {/* Phase 15: Gemini explains the analysis above. Loads independently; failure never affects the page. */}
          <div id="coin-ai-analysis" className="scroll-mt-40 lg:scroll-mt-28">
            <div className="-mb-3 mt-6"><DataKindBadge kind="ai" /></div>
            <AiAnalysisSection key={`ai-analysis-${coinId}`} coinId={coinId} />
          </div>
          <div id="coin-news" className="scroll-mt-40 lg:scroll-mt-28">
            <div className="-mb-3 mt-6"><DataKindBadge kind="observed" /></div>
            <CoinNewsSection key={`news-${coinId}`} coinId={coinId} coinName={coin.name} />
          </div>
        </>
      )}
    </AppShell>
  );
}
