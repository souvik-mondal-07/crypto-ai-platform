import { useEffect, useState } from "react";

import { fetchCoinHistory } from "../services/api/market.api";
import type { HistoricalCandle, Timeframe } from "../types/market";
import { toErrorMessage } from "../utils/apiErrors";
import { dedupe } from "../utils/dedupe";

interface HistoryState {
  candles: HistoricalCandle[];
  loading: boolean;
  error: string | null;
}

/**
 * Historical candles for one coin at one timeframe, for the Dashboard
 * performance chart. Reuses the existing `/coins/{id}/history` endpoint.
 *
 * Deliberately NOT polled: historical candles don't change meaningfully on a
 * 20-second cadence, and each call is a live provider request, so polling
 * would only spend rate limit. It refetches when the asset/timeframe changes
 * or on an explicit retry. A superseded response (user switched asset/range
 * quickly) is ignored via the `cancelled` flag.
 */
export function useAssetHistory(coinId: string | undefined, timeframe: Timeframe) {
  const [state, setState] = useState<HistoryState>({ candles: [], loading: false, error: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!coinId) {
      setState({ candles: [], loading: false, error: null });
      return;
    }

    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));

    dedupe(`asset-history:${coinId}:${timeframe}`, () => fetchCoinHistory(coinId, timeframe))
      .then((response) => {
        if (!cancelled) setState({ candles: response.candles, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            candles: [],
            loading: false,
            error: toErrorMessage(error, "Price history could not be loaded. Please retry."),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [coinId, timeframe, attempt]);

  return { ...state, retry: () => setAttempt((value) => value + 1) };
}
