import { useCallback, useEffect, useRef, useState } from "react";

import { fetchTechnicalAnalysis } from "../services/api/technicalAnalysis.api";
import type { Timeframe } from "../types/market";
import type { TechnicalAnalysisResponse } from "../types/technicalAnalysis";
import { ApiError } from "../types/apiError";

type LoadStatus = "idle" | "loading" | "success" | "error";

/**
 * Loads technical analysis for a coin, tracked independently of the
 * page's main coin/history load state — the RSI/MACD/etc. section can
 * show its own loading/error/empty state without blocking (or being
 * blocked by) the price chart above it.
 */
export function useTechnicalAnalysis(coinId: string | undefined, timeframe: Timeframe) {
  const [data, setData] = useState<TechnicalAnalysisResponse | null>(null);
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [insufficientData, setInsufficientData] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (!coinId) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setError(null);
    setInsufficientData(false);

    try {
      const result = await fetchTechnicalAnalysis(coinId, timeframe, controller.signal);
      if (controller.signal.aborted) return;
      setData(result);
      setStatus("success");
    } catch (caught) {
      if (controller.signal.aborted) return;
      const message = caught instanceof Error ? caught.message : "Unable to load technical analysis.";
      // Not enough historical data yet for this timeframe is a normal,
      // expected state for a thinly-traded or newly-listed coin — the
      // section should say so plainly rather than showing a generic error.
      // The backend signals this with INSUFFICIENT_HISTORICAL_DATA ("Only N candles are available ...;
      // at least M are needed ..."); the wording check covers callers without a code.
      const byCode = caught instanceof ApiError && caught.code === "INSUFFICIENT_HISTORICAL_DATA";
      setInsufficientData(byCode || /not enough|insufficient|candles are available|are needed to compute/i.test(message));
      setError(message);
      setStatus("error");
    }
  }, [coinId, timeframe]);

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  return {
    technicalAnalysis: data,
    loading: status === "loading",
    error: status === "error" ? error : null,
    insufficientData,
    refetch: load,
  };
}
