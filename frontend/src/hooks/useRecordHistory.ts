import { useEffect, useRef } from "react";

import { historyApi } from "../services/api/history.api";
import { useAuthStore } from "../store/authStore";
import type { AnalysisType } from "../types/userFeatures";

/**
 * Records "the signed-in user viewed this analysis" once per coin per mount, after the analysis has
 * actually loaded (`ready`). Fire-and-forget: a failure never affects the page. The backend decides the
 * outcome (decision / risk level / status) from what is stored and ignores repeats within a few minutes.
 */
export function useRecordHistory(coinId: string | undefined, type: AnalysisType, ready: boolean): void {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const recorded = useRef<string | null>(null);

  useEffect(() => {
    if (!coinId || !ready || !isAuthenticated || recorded.current === coinId) return;
    recorded.current = coinId;
    historyApi.record(coinId, type).catch(() => {
      // History is a convenience; never surface its failures on the analysis itself.
    });
  }, [coinId, type, ready, isAuthenticated]);
}
