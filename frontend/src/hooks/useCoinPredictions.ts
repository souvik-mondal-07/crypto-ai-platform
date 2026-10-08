import { useCallback, useEffect, useRef, useState } from "react";

import { fetchCoinPredictions } from "../services/api/predictions.api";
import type { PredictionListResponse } from "../types/predictions";
import { describePredictionError, type PredictionErrorKind } from "../utils/predictionErrors";

interface Loaded {
  coinId: string;
  value: PredictionListResponse;
}

/**
 * Model predictions for a coin. Data is stored with the coin it belongs to and only
 * exposed while it matches, so switching coins never briefly shows the previous
 * coin's prediction. Always settles into data or error — never stuck loading.
 */
export function useCoinPredictions(coinId: string | undefined) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<{ kind: PredictionErrorKind; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!coinId) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setError(null);
    fetchCoinPredictions(coinId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setLoaded({ coinId, value });
        setStatus("success");
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(describePredictionError(caught));
        setStatus("error");
      });

    return () => controller.abort();
  }, [coinId, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  const data = loaded && loaded.coinId === coinId ? loaded.value : null;

  return {
    data,
    loading: status === "loading" && data === null,
    error: status === "error" && data === null ? error : null,
    retry,
  };
}
