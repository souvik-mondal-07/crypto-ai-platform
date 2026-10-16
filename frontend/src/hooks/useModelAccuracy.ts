import { useCallback, useEffect, useState } from "react";

import { backtestingApi } from "../services/api/backtesting.api";
import type { AccuracyFilters, AccuracyResponse, DecisionEvaluation } from "../types/backtesting";
import { toErrorMessage } from "../utils/apiErrors";

export const REFRESH_POLL_MS = 2500;
const NO_FILTERS: AccuracyFilters = { horizon: "", modelVersion: "", coinId: "" };

export interface RefreshUiState {
  running: boolean;
  message: string | null;
  error: string | null;
}

/** Prediction accuracy from the stored, matched outcomes (reads only) plus the explicit "update outcomes" action. */
export function useModelAccuracy() {
  const [filters, setFilters] = useState<AccuracyFilters>(NO_FILTERS);
  const [data, setData] = useState<AccuracyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [refresh, setRefresh] = useState<RefreshUiState>({ running: false, message: null, error: null });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    backtestingApi
      .accuracy(filters)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(toErrorMessage(caught, "Model accuracy could not be loaded."));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, attempt]);

  // While a refresh runs on the server, poll its state; reload the metrics once it finishes.
  useEffect(() => {
    if (!refresh.running) return;
    let cancelled = false;
    const id = window.setInterval(() => {
      backtestingApi
        .refreshStatus()
        .then((state) => {
          if (cancelled || state.running) return;
          setRefresh({ running: false, message: state.last_error ? null : "Outcomes updated.", error: state.last_error });
          setAttempt((value) => value + 1);
        })
        .catch((caught: unknown) => {
          if (cancelled) return;
          setRefresh({ running: false, message: null, error: toErrorMessage(caught, "Could not check the outcome update.") });
        });
    }, REFRESH_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [refresh.running]);

  const startRefresh = useCallback(async () => {
    setRefresh({ running: true, message: null, error: null });
    try {
      const state = await backtestingApi.refreshOutcomes();
      if (!state.running) {
        setRefresh({ running: false, message: state.message, error: state.last_error });
        setAttempt((value) => value + 1);
      }
    } catch (caught) {
      setRefresh({ running: false, message: null, error: toErrorMessage(caught, "Outcome update could not be started.") });
    }
  }, []);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  const changeFilters = useCallback((patch: Partial<AccuracyFilters>) => setFilters((current) => ({ ...current, ...patch })), []);

  return { filters, changeFilters, data, loading, error, retry, refresh, startRefresh };
}

/** BUY/HOLD/SELL evaluated against the return that followed (stored results only). */
export function useDecisionEvaluation() {
  const [horizon, setHorizon] = useState("");
  const [data, setData] = useState<DecisionEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    backtestingApi
      .decisions(horizon || undefined)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(toErrorMessage(caught, "Decision evaluation could not be loaded."));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [horizon, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { horizon, setHorizon, data, loading, error, retry };
}
