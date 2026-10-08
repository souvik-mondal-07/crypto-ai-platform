import { useCallback, useEffect, useRef, useState } from "react";

import { fetchNews } from "../services/api/news.api";
import type { NewsListResponse, NewsQuery } from "../types/news";
import { describeNewsError, type NewsErrorKind } from "../utils/newsErrors";

/**
 * Loads one page of news (global feed, or a coin's feed when `coinId` is set).
 *
 * - Every request ends in success or error (the axios timeout guarantees it) —
 *   there is no state that can spin forever.
 * - A newer request aborts the previous one, and a response for a superseded
 *   request is discarded, so fast filter/page changes can't show stale data.
 * - When the page or a filter changes, the previous list stays on screen
 *   (`refreshing`) instead of blanking; `loading` is true only when there is
 *   nothing to show yet.
 */
export function useNewsList(query: NewsQuery, enabled = true) {
  const [loaded, setLoaded] = useState<{ coinId: string | undefined; response: NewsListResponse } | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<{ kind: NewsErrorKind; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  // A stable key so an inline `query` object doesn't retrigger the effect each render.
  const key = JSON.stringify(query);

  useEffect(() => {
    if (!enabled) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setError(null);
    fetchNews(JSON.parse(key) as NewsQuery, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setLoaded({ coinId: query.coinId, response });
        setStatus("success");
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(describeNewsError(caught));
        setStatus("error");
      });

    return () => controller.abort();
    // `query` is represented by `key`; reading query.coinId inside the callbacks is intentional.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  // Page/filter changes keep the previous list visible; a different coin never shows another coin's news.
  const data = loaded && loaded.coinId === query.coinId ? loaded.response : null;

  return {
    data,
    loading: status === "loading" && data === null,
    refreshing: status === "loading" && data !== null,
    error: status === "error" ? error : null,
    retry,
  };
}
