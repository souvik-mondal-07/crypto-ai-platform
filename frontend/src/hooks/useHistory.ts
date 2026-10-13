import { useCallback, useEffect, useState } from "react";

import { historyApi } from "../services/api/history.api";
import type { AnalysisType, HistoryList } from "../types/userFeatures";
import { toErrorMessage } from "../utils/apiErrors";
import { toast } from "../store/toastStore";

export const HISTORY_PAGE_SIZE = 20;

/** The signed-in user's analysis history: newest first, paginated, optionally filtered. Always settles. */
export function useHistory() {
  const [page, setPage] = useState(1);
  const [analysisType, setAnalysisType] = useState<AnalysisType | "">("");
  const [data, setData] = useState<HistoryList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    historyApi
      .list({ page, limit: HISTORY_PAGE_SIZE, analysisType: analysisType || undefined })
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(toErrorMessage(caught, "Your history could not be loaded."));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, analysisType, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  const changeType = useCallback((next: AnalysisType | "") => {
    setPage(1);
    setAnalysisType(next);
  }, []);

  const remove = useCallback(
    async (id: string) => {
      setActionError(null);
      try {
        await historyApi.remove(id);
        toast.success("History entry deleted.");
        // Step back a page if that was the last row on this one.
        if (data && data.items.length === 1 && page > 1) setPage(page - 1);
        else setAttempt((value) => value + 1);
      } catch (caught) {
        setActionError(toErrorMessage(caught, "That entry could not be deleted."));
      }
    },
    [data, page]
  );

  return { data, loading, error, actionError, page, setPage, analysisType, changeType, retry, remove };
}
