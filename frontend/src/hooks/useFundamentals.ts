import { useCallback, useEffect, useRef, useState } from "react";

import { fetchFundamentals } from "../services/api/fundamentals.api";
import { ApiError } from "../types/apiError";
import type { FundamentalAnalysisResponse } from "../types/fundamentals";

type LoadStatus = "idle" | "loading" | "success" | "error";

interface Loaded {
  coinId: string;
  value: FundamentalAnalysisResponse;
}

/** Backend code meaning "this coin genuinely has no fundamental data" (as opposed to a failed request). */
export const FUNDAMENTALS_NOT_AVAILABLE_CODE = "FUNDAMENTALS_NOT_AVAILABLE";

/**
 * Loads fundamental analysis for a coin, tracked independently of the
 * page's coin/history/technical-analysis state so this section can show
 * its own loading, error and empty states.
 *
 * - Data is stored together with the coin it belongs to and only exposed
 *   while it matches the current coin, so navigating to another coin can
 *   never briefly show the previous coin's numbers.
 * - A refresh keeps the current data on screen (`refreshing`) instead of
 *   blanking it; if that refresh fails, the data stays and `error` is set.
 * - Every request ends in success or error — there is no state that can
 *   spin forever.
 */
export function useFundamentals(coinId: string | undefined) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(
    async (forceRefresh: boolean) => {
      if (!coinId) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setStatus("loading");
      setError(null);
      setNotAvailable(false);

      try {
        const result = await fetchFundamentals(coinId, { forceRefresh, signal: controller.signal });
        if (controller.signal.aborted) return;
        setLoaded({ coinId, value: result });
        setStatus("success");
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : "Unable to load fundamental analysis.");
        setNotAvailable(caught instanceof ApiError && caught.code === FUNDAMENTALS_NOT_AVAILABLE_CODE);
        setStatus("error");
      }
    },
    [coinId]
  );

  useEffect(() => {
    load(false);
    return () => abortRef.current?.abort();
  }, [load]);

  const refetch = useCallback(() => load(false), [load]);
  const refresh = useCallback(() => load(true), [load]);

  const fundamentals = loaded && loaded.coinId === coinId ? loaded.value : null;

  return {
    fundamentals,
    /** Initial load (nothing to show yet). */
    loading: status === "loading" && fundamentals === null,
    /** A reload while existing data is still displayed. */
    refreshing: status === "loading" && fundamentals !== null,
    error: status === "error" ? error : null,
    notAvailable: status === "error" && notAvailable,
    /** Re-run the normal (cache-friendly) request. */
    refetch,
    /** Ask the backend to re-fetch provider project data (rate-limited server-side). */
    refresh,
  };
}
