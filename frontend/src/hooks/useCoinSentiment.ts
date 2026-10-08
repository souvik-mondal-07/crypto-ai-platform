import { useCallback, useEffect, useRef, useState } from "react";

import { fetchCoinSentiment } from "../services/api/news.api";
import type { CoinSentimentResponse, SentimentTimeframe } from "../types/news";
import { describeNewsError, type NewsErrorKind } from "../utils/newsErrors";

interface Loaded {
  coinId: string;
  timeframe: SentimentTimeframe;
  value: CoinSentimentResponse;
}

/**
 * Aggregated news sentiment for a coin and period. Data is stored together
 * with the coin/timeframe it belongs to and only exposed while both match, so
 * switching coin or period can never briefly show the previous numbers.
 */
export function useCoinSentiment(coinId: string | undefined, timeframe: SentimentTimeframe) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<{ kind: NewsErrorKind; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!coinId) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setError(null);
    fetchCoinSentiment(coinId, timeframe, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setLoaded({ coinId, timeframe, value });
        setStatus("success");
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(describeNewsError(caught));
        setStatus("error");
      });

    return () => controller.abort();
  }, [coinId, timeframe, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  const sentiment = loaded && loaded.coinId === coinId && loaded.timeframe === timeframe ? loaded.value : null;

  return {
    sentiment,
    loading: status === "loading" && sentiment === null,
    error: status === "error" ? error : null,
    retry,
  };
}
