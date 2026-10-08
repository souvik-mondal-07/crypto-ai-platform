import { useEffect, useState } from "react";

import { searchCoins } from "../services/api/coins.api";
import type { CoinSearchResult } from "../types/coin";
import { toErrorMessage } from "../utils/apiErrors";
import { dedupe } from "../utils/dedupe";
import { useDebouncedValue } from "./useDebouncedValue";

interface SearchState {
  results: CoinSearchResult[];
  loading: boolean;
  error: string | null;
  /** The (trimmed) query these results belong to. */
  settledQuery: string;
}

/**
 * Suggestion search for the header box and Ctrl+K palette. Uses the existing
 * backend `/coins/search` (name / symbol / slug, joined with market data) —
 * it never filters a local list. Keystrokes are debounced; a response for an
 * outdated query is discarded so suggestions can't flicker back to old text.
 *
 * Intentionally independent of marketStore's search slice, which belongs to
 * the Markets table: typing in the header must not rewrite the table.
 */
export function useCoinSearch(rawQuery: string, limit = 8, enabled = true) {
  const debounced = useDebouncedValue(rawQuery, 250).trim();
  const [state, setState] = useState<SearchState>({ results: [], loading: false, error: null, settledQuery: "" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled || !debounced) {
      setState({ results: [], loading: false, error: null, settledQuery: "" });
      return;
    }
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));

    dedupe(`coin-search:${limit}:${debounced.toLowerCase()}`, () => searchCoins(debounced, limit))
      .then((response) => {
        if (!cancelled) setState({ results: response.items, loading: false, error: null, settledQuery: debounced });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            results: [],
            loading: false,
            error: toErrorMessage(error, "Search failed. Please retry."),
            settledQuery: debounced,
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [debounced, limit, enabled, attempt]);

  const waiting = rawQuery.trim() !== debounced; // user is still typing
  return {
    ...state,
    loading: state.loading || (enabled && waiting && rawQuery.trim() !== ""),
    hasQuery: debounced !== "",
    retry: () => setAttempt((value) => value + 1),
  };
}
