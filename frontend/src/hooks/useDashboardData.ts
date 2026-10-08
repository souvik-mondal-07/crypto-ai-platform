import { useCallback, useEffect } from "react";

import { env } from "../config/environment";
import { useDashboardStore } from "../store/dashboardStore";
import { usePolling } from "./usePolling";

/**
 * Loads and refreshes the Dashboard-only datasets (heatmap + the BTC/ETH
 * lookup that feeds the performance chart) in ONE place, on the shared
 * `marketRefreshIntervalMs` cadence. Components below read from the store
 * and never start their own polling, so a section appearing twice cannot
 * double the request rate. Identical overlapping requests are additionally
 * coalesced in the store (utils/dedupe.ts).
 */
export function useDashboardData() {
  const heatmap = useDashboardStore((state) => state.heatmap);
  const fetchHeatmap = useDashboardStore((state) => state.fetchHeatmap);

  useEffect(() => {
    fetchHeatmap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  usePolling(() => {
    fetchHeatmap({ silent: true });
  }, env.marketRefreshIntervalMs);

  const refetch = useCallback(() => {
    fetchHeatmap();
  }, [fetchHeatmap]);

  return { heatmap, refetch };
}
