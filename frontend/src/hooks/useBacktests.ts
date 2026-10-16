import { useCallback, useEffect, useState } from "react";

import { backtestingApi } from "../services/api/backtesting.api";
import type {
  BacktestConfig,
  BacktestRequest,
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestTrade,
  Paged,
} from "../types/backtesting";
import { toErrorMessage } from "../utils/apiErrors";

export const RUN_POLL_MS = 2000;
export const TRADES_PAGE_SIZE = 25;

/** Engine defaults, supported options and limits (nothing about them is hard-coded in the UI). */
export function useBacktestConfig() {
  const [config, setConfig] = useState<BacktestConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    backtestingApi
      .config()
      .then((result) => {
        if (!cancelled) setConfig(result);
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(toErrorMessage(caught, "Backtest options could not be loaded."));
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  return { config, error, retry: useCallback(() => setAttempt((v) => v + 1), []) };
}

const isActive = (status: string | undefined) => status === "queued" || status === "running";

/** The user's own backtest runs: create, list, follow one run while it is queued/running, page its trades. */
export function useBacktests() {
  const [runs, setRuns] = useState<Paged<BacktestRunSummary> | null>(null);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<BacktestRunDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [tradesPage, setTradesPage] = useState(1);
  const [trades, setTrades] = useState<Paged<BacktestTrade> | null>(null);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [listAttempt, setListAttempt] = useState(0);
  const [detailAttempt, setDetailAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setRunsError(null);
    backtestingApi
      .listRuns(1, 10)
      .then((result) => {
        if (cancelled) return;
        setRuns(result);
        setRunsLoading(false);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setRunsError(toErrorMessage(caught, "Your backtest runs could not be loaded."));
        setRunsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [listAttempt]);

  // Load the selected run; while it is queued/running keep polling until it settles.
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    let timer: number | undefined;
    const load = (first: boolean) => {
      if (first) setDetailLoading(true);
      backtestingApi
        .getRun(selectedId)
        .then((result) => {
          if (cancelled) return;
          setDetail(result);
          setDetailError(null);
          setDetailLoading(false);
          if (isActive(result.status)) {
            timer = window.setTimeout(() => load(false), RUN_POLL_MS);
          } else {
            setListAttempt((value) => value + 1);
          }
        })
        .catch((caught: unknown) => {
          if (cancelled) return;
          setDetailError(toErrorMessage(caught, "This backtest could not be loaded."));
          setDetailLoading(false);
        });
    };
    load(true);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [selectedId, detailAttempt]);

  const finished = detail !== null && detail.run_id === selectedId && !isActive(detail.status) && detail.trade_count > 0;
  useEffect(() => {
    if (!selectedId || !finished) {
      setTrades(null);
      return;
    }
    let cancelled = false;
    setTradesError(null);
    backtestingApi
      .runTrades(selectedId, tradesPage, TRADES_PAGE_SIZE)
      .then((result) => {
        if (!cancelled) setTrades(result);
      })
      .catch((caught: unknown) => {
        if (!cancelled) setTradesError(toErrorMessage(caught, "Trades could not be loaded."));
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, finished, tradesPage]);

  const select = useCallback((runId: string | null) => {
    setTradesPage(1);
    setDetailError(null);
    setSelectedId(runId);
  }, []);

  const submit = useCallback(
    async (body: BacktestRequest): Promise<boolean> => {
      setSubmitting(true);
      setSubmitError(null);
      try {
        const created = await backtestingApi.createRun(body);
        setDetail(null);
        select(created.run_id);
        setListAttempt((value) => value + 1);
        return true;
      } catch (caught) {
        setSubmitError(toErrorMessage(caught, "The backtest could not be started."));
        return false;
      } finally {
        setSubmitting(false);
      }
    },
    [select]
  );

  return {
    runs, runsLoading, runsError, retryRuns: useCallback(() => setListAttempt((v) => v + 1), []),
    selectedId, select, detail, detailLoading, detailError, retryDetail: useCallback(() => setDetailAttempt((v) => v + 1), []),
    submit, submitting, submitError, clearSubmitError: useCallback(() => setSubmitError(null), []),
    trades, tradesPage, setTradesPage, tradesError,
  };
}
