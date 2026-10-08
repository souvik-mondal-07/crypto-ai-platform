import { useCallback, useEffect, useRef, useState } from "react";

import { fetchDecision } from "../services/api/decisions.api";
import type { DecisionResponse } from "../types/decisions";
import { describeDecisionError } from "../utils/decisionErrors";

interface Loaded {
  coinId: string;
  value: DecisionResponse;
}

/**
 * Risk & Decision for a coin. The result is calculated and cached by the backend, so this hook
 * requests it once per coin (and on Retry) — it never recalculates on re-render. Data is stored
 * with the coin it belongs to and only exposed while it matches, so switching coins never
 * briefly shows the previous coin's decision. Always settles into data or error.
 */
export function useCoinDecision(coinId: string | undefined) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const forceRef = useRef(false);

  useEffect(() => {
    if (!coinId) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const forceRefresh = forceRef.current;
    forceRef.current = false;

    setStatus("loading");
    setError(null);
    fetchDecision(coinId, { forceRefresh, signal: controller.signal })
      .then((value) => {
        if (controller.signal.aborted) return;
        setLoaded({ coinId, value });
        setStatus("success");
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(describeDecisionError(caught).message);
        setStatus("error");
      });

    return () => controller.abort();
  }, [coinId, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  /** Ask the backend to recalculate now (the data stays on screen while it does). */
  const refresh = useCallback(() => {
    forceRef.current = true;
    setAttempt((value) => value + 1);
  }, []);

  const data = loaded && loaded.coinId === coinId ? loaded.value : null;
  return {
    data,
    loading: status === "loading" && data === null,
    refreshing: status === "loading" && data !== null,
    error: status === "error" && data === null ? error : null,
    retry,
    refresh,
  };
}
