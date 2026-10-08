import { useEffect, useState } from "react";

import { fetchTrending } from "../services/api/market.api";
import { toErrorMessage } from "../utils/apiErrors";
import { dedupe } from "../utils/dedupe";

interface TrendingState {
  /** Internal ids of trending coins that exist in our own database (unsynced ones can't be linked). */
  ids: string[];
  /** false when the provider doesn't offer trending — shown as such, not as "no trending coins". */
  available: boolean;
  loading: boolean;
  error: string | null;
}

/** Fetches trending coins only while `enabled` (the Trending tab is open). Not polled — it's a live provider call. */
export function useTrendingCoinIds(enabled: boolean) {
  const [state, setState] = useState<TrendingState>({ ids: [], available: true, loading: enabled, error: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));
    dedupe("market-trending", () => fetchTrending())
      .then((response) => {
        if (cancelled) return;
        const ids = response.items
          .map((item) => item.internal_coin_id)
          .filter((id): id is string => typeof id === "string" && id.length > 0);
        setState({ ids, available: response.available, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({ ids: [], available: true, loading: false, error: toErrorMessage(error, "Trending coins could not be loaded. Please retry.") });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, attempt]);

  return { ...state, retry: () => setAttempt((value) => value + 1) };
}
