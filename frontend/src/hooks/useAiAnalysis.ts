import { useCallback, useEffect, useRef, useState } from "react";

import { fetchAiAnalysis, generateAiAnalysis } from "../services/api/aiAnalysis.api";
import type { AiAnalysisResponse } from "../types/aiAnalysis";
import { describeAiError, isNoAnalysisYet, logAiError, type AiErrorInfo } from "../utils/aiAnalysisErrors";

interface Loaded {
  coinId: string;
  value: AiAnalysisResponse;
}

type Phase = "idle" | "loading" | "generating" | "ready" | "error";

/** Client-side floor between manual regenerations, on top of the backend's own cooldown. */
export const REGENERATE_COOLDOWN_MS = 30_000;

/**
 * AI explanation for a coin (Phase 15).
 *
 * Request policy (this is the cost protection on the browser side):
 *  - One effect run per coin (and per Retry): re-renders never call the backend.
 *  - It first READS the stored explanation (never calls Gemini). Only when none exists — or the stored
 *    one has expired / no longer matches the Phase 14 decision — it asks the backend to generate, once;
 *    the backend itself returns a fresh stored one without calling Gemini when it can.
 *  - Manual `regenerate()` is ignored while a request is in flight or a cooldown is active.
 *  - Data is stored with its coin and only exposed while it matches (no flash of another coin's text).
 *  - A failure while an explanation is already on screen is a note, not a replacement of that text.
 */
export function useAiAnalysis(coinId: string | undefined) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<AiErrorInfo | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [cooldownUntil, setCooldownUntil] = useState<number | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const inFlightRef = useRef(false);
  const cooldownRef = useRef<number | null>(null);
  const modeRef = useRef<"auto" | "regenerate">("auto");

  const applyCooldown = useCallback((until: number | null) => {
    cooldownRef.current = until;
    setCooldownUntil(until);
  }, []);

  useEffect(() => {
    if (!coinId) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const { signal } = controller;
    const mode = modeRef.current;
    modeRef.current = "auto";
    inFlightRef.current = true;
    setError(null);
    setNote(null);

    const commit = (value: AiAnalysisResponse) => {
      setLoaded({ coinId, value });
      setPhase("ready");
      const next = value.next_regeneration_at ? Date.parse(value.next_regeneration_at) : null;
      if (next !== null && !Number.isNaN(next) && next > Date.now()) applyCooldown(Math.max(next, cooldownRef.current ?? 0));
    };

    const run = async () => {
      try {
        if (mode === "regenerate") {
          setPhase("generating");
          commit(await generateAiAnalysis(coinId, { forceRefresh: true, signal }));
          return;
        }

        setPhase("loading");
        let stored: AiAnalysisResponse | null = null;
        try {
          stored = await fetchAiAnalysis(coinId, { signal });
        } catch (caught) {
          if (signal.aborted) return;
          if (!isNoAnalysisYet(caught)) throw caught;
        }

        if (stored === null) {
          setPhase("generating");
          commit(await generateAiAnalysis(coinId, { signal }));
          return;
        }

        commit(stored);
        if (stored.is_stale || stored.is_outdated) {
          // Show what we have while the backend decides whether a new call is warranted.
          setPhase("generating");
          try {
            commit(await generateAiAnalysis(coinId, { signal }));
          } catch (caught) {
            if (signal.aborted) return;
            logAiError("refreshing the stored analysis", caught);
            setNote(describeAiError(caught).message);
            setPhase("ready");
          }
        }
      } catch (caught) {
        if (signal.aborted) return;
        logAiError(mode === "regenerate" ? "regenerating" : "loading", caught);
        const info = describeAiError(caught);
        if (mode === "regenerate") {
          // Keep the explanation that is on screen; just say why a new one was not produced.
          setNote(info.message);
          setPhase("ready");
          if (info.kind === "rate_limited" || info.kind === "cooldown") applyCooldown(Date.now() + REGENERATE_COOLDOWN_MS);
        } else {
          setError(info);
          setPhase("error");
        }
      } finally {
        if (!signal.aborted) inFlightRef.current = false;
      }
    };

    void run();
    return () => {
      controller.abort();
      inFlightRef.current = false;
    };
  }, [coinId, attempt, applyCooldown]);

  /** Re-run the load (read, then generate if nothing is stored). Ignored while a request is running. */
  const retry = useCallback(() => {
    if (inFlightRef.current) return;
    setAttempt((value) => value + 1);
  }, []);

  /** Ask for a NEW explanation. Ignored while a request is running or a cooldown is active. */
  const regenerate = useCallback(() => {
    if (inFlightRef.current) return;
    if (cooldownRef.current !== null && cooldownRef.current > Date.now()) return;
    modeRef.current = "regenerate";
    applyCooldown(Date.now() + REGENERATE_COOLDOWN_MS);
    setAttempt((value) => value + 1);
  }, [applyCooldown]);

  const data = loaded && loaded.coinId === coinId ? loaded.value : null;
  return {
    data,
    loading: phase === "loading" && data === null,
    generating: phase === "generating" && data === null,
    refreshing: phase === "generating" && data !== null,
    error: phase === "error" && data === null ? error : null,
    note,
    cooldownUntil,
    retry,
    regenerate,
  };
}
