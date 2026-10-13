import { useCallback, useEffect, useRef, useState } from "react";

import { env } from "../config/environment";
import { fetchCoinById } from "../services/api/coins.api";
import { fetchCoinHistory, fetchCoinMarketData } from "../services/api/market.api";
import type { Coin } from "../types/coin";
import type { HistoricalCandle, MarketData, Timeframe } from "../types/market";
import { usePolling } from "./usePolling";

type LoadStatus = "idle" | "loading" | "success" | "error";

/**
 * Loads everything the Coin Details page needs, with the coin/market
 * request and the history request tracked independently — the header
 * and stats can render while the chart is still loading, rather than
 * the whole page waiting on the slowest call.
 *
 * `notFound` is distinguished from a generic error so the page can
 * show a proper "Cryptocurrency not found" state.
 */
export function useCoinDetails(coinId: string | undefined) {
  const [coin, setCoin] = useState<Coin | null>(null);
  const [market, setMarket] = useState<MarketData | null>(null);
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [timeframe, setTimeframe] = useState<Timeframe>("7D");
  const [candles, setCandles] = useState<HistoricalCandle[]>([]);
  const [granularity, setGranularity] = useState<string | null>(null);
  const [historyStatus, setHistoryStatus] = useState<LoadStatus>("idle");
  const [historyError, setHistoryError] = useState<string | null>(null);

  // Tracks the in-flight history request so a rapid timeframe change
  // aborts the previous one instead of letting a stale response win.
  const historyAbortRef = useRef<AbortController | null>(null);

  const loadCoin = useCallback(async () => {
    if (!coinId) return;
    setStatus("loading");
    setError(null);
    setNotFound(false);

    try {
      const coinResult = await fetchCoinById(coinId);
      setCoin(coinResult);

      // Market data may legitimately not exist yet for a coin that
      // hasn't been through a market-data sync — that's not a page
      // error, just a missing section.
      try {
        setMarket(await fetchCoinMarketData(coinId));
      } catch {
        setMarket(null);
      }

      setStatus("success");
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Unable to load this cryptocurrency.";
      // The backend returns a distinct message for a missing coin ("No coin found with id '…'.");
      // treat that as not-found rather than a generic failure.
      setNotFound(/not found/i.test(message) || /no coin found/i.test(message) || /not a valid identifier/i.test(message));
      setError(message);
      setStatus("error");
    }
  }, [coinId]);

  const loadHistory = useCallback(async () => {
    if (!coinId) return;

    historyAbortRef.current?.abort();
    const controller = new AbortController();
    historyAbortRef.current = controller;

    setHistoryStatus("loading");
    setHistoryError(null);

    try {
      const result = await fetchCoinHistory(coinId, timeframe, controller.signal);
      if (controller.signal.aborted) return;
      setCandles(result.candles);
      setGranularity(result.granularity);
      setHistoryStatus("success");
    } catch (caught) {
      if (controller.signal.aborted) return;
      setHistoryError(caught instanceof Error ? caught.message : "Unable to load historical data.");
      setHistoryStatus("error");
    }
  }, [coinId, timeframe]);

  // Silent background refresh of ONLY the current market snapshot
  // (price, 24h change, stale flag, etc.) — Part 12. Deliberately
  // does not re-fetch coin identity or OHLCV history: those don't
  // change on this cadence, and re-fetching them on every tick would
  // multiply request volume for no benefit. A failed background tick
  // is not surfaced as a page error — the last good market snapshot
  // (with its own `is_stale` flag) simply stays on screen.
  const refreshMarketSnapshot = useCallback(async () => {
    if (!coinId) return;
    try {
      setMarket(await fetchCoinMarketData(coinId));
    } catch {
      // leave the last known market snapshot in place
    }
  }, [coinId]);

  useEffect(() => {
    loadCoin();
  }, [loadCoin]);

  // Refetches only when coinId or timeframe actually changes — not on
  // unrelated re-renders (loadHistory is memoized on exactly those two).
  useEffect(() => {
    loadHistory();
    return () => historyAbortRef.current?.abort();
  }, [loadHistory]);

  usePolling(refreshMarketSnapshot, env.marketRefreshIntervalMs, Boolean(coinId));

  return {
    coin,
    market,
    loading: status === "loading",
    error: status === "error" ? error : null,
    notFound,
    refetch: loadCoin,

    timeframe,
    setTimeframe,
    candles,
    granularity,
    historyLoading: historyStatus === "loading",
    historyError,
    refetchHistory: loadHistory,
  };
}
