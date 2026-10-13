import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, ArrowRight, Lightbulb, MessageSquare, Sparkles, type LucideIcon } from "lucide-react";

import { fetchAiAnalysis } from "../../services/api/aiAnalysis.api";
import type { AiAnalysisResponse } from "../../types/aiAnalysis";
import { describeAiError, isNoAnalysisYet } from "../../utils/aiAnalysisErrors";
import { RetryError } from "../common/RetryError";
import { Skeleton } from "../ui/Skeleton";

export interface InsightCoin {
  coin_id: string;
  name: string;
  symbol: string;
}

type State =
  | { kind: "loading" }
  | { kind: "ready"; analysis: AiAnalysisResponse }
  | { kind: "none" }
  | { kind: "error"; message: string };

const DOT = { up: "bg-emerald-400", down: "bg-rose-400", warn: "bg-amber-400", info: "bg-brand-400" } as const;

function Section({ title, icon: Icon, tone = "text-brand-400", children }: { title: string; icon: LucideIcon; tone?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 dark:border-brand-500/20 dark:bg-white/[0.03]">
      <h3 className="flex items-center gap-2 text-xs font-semibold text-slate-800 dark:text-slate-100">
        <Icon className={`h-4 w-4 ${tone}`} aria-hidden="true" />
        {title}
      </h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Bullets({ items, tone }: { items: string[]; tone: keyof typeof DOT }) {
  return (
    <ul className="space-y-1">
      {items.slice(0, 3).map((item) => (
        <li key={item} className="flex gap-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          <span aria-hidden="true" className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${DOT[tone]}`} />
          <span className="line-clamp-3">{item}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Dashboard AI panel: shows the STORED Gemini explanation for the largest coin in the dataset. It only ever
 * READS an existing explanation (GET) — it never asks Gemini to generate one, so opening the Dashboard costs no
 * AI calls; generating happens on the coin's own page. Everything shown is returned text; nothing is invented.
 */
export function AiInsightsPanel({ coin, coinsLoading = false }: { coin: InsightCoin | null; coinsLoading?: boolean }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const coinId = coin?.coin_id;

  useEffect(() => {
    if (!coinId) return;
    const controller = new AbortController();
    setState({ kind: "loading" });
    fetchAiAnalysis(coinId, { signal: controller.signal })
      .then((analysis) => setState({ kind: "ready", analysis }))
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setState(isNoAnalysisYet(caught) ? { kind: "none" } : { kind: "error", message: describeAiError(caught).message });
      });
    return () => controller.abort();
  }, [coinId, attempt]);

  const detailPath = coin ? `/coins/${coin.coin_id}#coin-ai-analysis` : "/markets";

  return (
    <section aria-labelledby="ai-insights-heading" className="ai-surface flex h-full flex-col p-4 sm:p-5">
      <div aria-hidden="true" className="pointer-events-none absolute -right-10 -top-12 h-40 w-40 animate-glow rounded-full bg-brand-violet/30 blur-3xl motion-reduce:animate-none" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-16 -left-10 h-40 w-40 rounded-full bg-brand-500/20 blur-3xl" />

      <header className="relative flex items-start gap-3">
        <span className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-violet text-white shadow-glow-violet">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h2 id="ai-insights-heading" className="text-base font-semibold text-slate-900 dark:text-white">AI Market Insights</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Powered by Gemini{coin ? ` · ${coin.name}` : ""}
          </p>
        </div>
      </header>

      <div className="relative mt-4 flex-1 space-y-3">
        {!coin && !coinsLoading ? (
          <p className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-white/15 dark:text-slate-400">
            AI insights appear once market data is available.
          </p>
        ) : !coin || state.kind === "loading" ? (
          <div role="status" aria-label="Loading AI insights" className="space-y-3">
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-20 w-full rounded-xl" />
            <Skeleton className="h-20 w-full rounded-xl" />
          </div>
        ) : state.kind === "error" ? (
          <RetryError message={state.message} onRetry={() => setAttempt((value) => value + 1)} compact />
        ) : state.kind === "none" ? (
          <p className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-white/15 dark:text-slate-400">
            No AI explanation has been generated for {coin.name} yet. Open its page to generate one.
          </p>
        ) : (
          <>
            <Section title="Market Sentiment" icon={MessageSquare}>
              <p className="line-clamp-5 text-xs leading-relaxed text-slate-600 dark:text-slate-300">{state.analysis.analysis.summary}</p>
              <p className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-500">AI-generated interpretation, not market data.</p>
            </Section>
            {state.analysis.analysis.bullish_factors.length > 0 && (
              <Section title="Key Observations" icon={Lightbulb} tone="text-emerald-400">
                <Bullets items={state.analysis.analysis.bullish_factors} tone="up" />
                {state.analysis.analysis.bearish_factors.length > 0 && (
                  <>
                    <p className="mb-1 mt-2 text-[11px] font-medium text-slate-500 dark:text-slate-400">Bearish factors</p>
                    <Bullets items={state.analysis.analysis.bearish_factors} tone="down" />
                  </>
                )}
              </Section>
            )}
            {state.analysis.decision_snapshot.decision && (
              <Section title="Technical Signals" icon={Activity} tone="text-cyan-300">
                <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  Platform decision: <span className="font-semibold text-slate-900 dark:text-white">{state.analysis.decision_snapshot.decision}</span>
                  {state.analysis.decision_snapshot.risk_level ? <> · Risk: <span className="font-semibold text-slate-900 dark:text-white">{state.analysis.decision_snapshot.risk_level}</span></> : null}
                </p>
                <p className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-500">Computed by the platform's decision engine from technical, fundamental, sentiment and risk data; the AI only explains it.</p>
              </Section>
            )}
            {state.analysis.analysis.key_risks.length > 0 && (
              <Section title="Risk Warnings" icon={AlertTriangle} tone="text-amber-400">
                <Bullets items={state.analysis.analysis.key_risks} tone="warn" />
              </Section>
            )}
            <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-500">{state.analysis.disclaimer}</p>
          </>
        )}
      </div>

      <Link to={detailPath} className="btn-gradient relative mt-4 w-full">
        View Detailed Analysis
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
    </section>
  );
}
