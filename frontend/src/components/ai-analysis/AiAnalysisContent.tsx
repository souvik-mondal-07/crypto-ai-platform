import { AlertTriangle } from "lucide-react";

import type { AiAnalysisResponse, AiInputModule } from "../../types/aiAnalysis";
import { formatAbsoluteDateTime, formatRelativeTime } from "../../utils/formatters";
import { AiFactorList } from "./AiFactorList";

const RISK_LEVEL_LABEL: Record<string, string> = {
  VERY_LOW: "Very low",
  LOW: "Low",
  MODERATE: "Moderate",
  HIGH: "High",
  VERY_HIGH: "Very high",
};

interface SectionSpec {
  title: string;
  field: "market_analysis" | "technical_analysis" | "fundamental_analysis" | "sentiment_analysis" | "prediction_analysis" | "risk_analysis" | "decision_explanation";
  /** Inputs whose unavailability affects this section. */
  inputs: AiInputModule[];
}

const SECTIONS: SectionSpec[] = [
  { title: "Market Interpretation", field: "market_analysis", inputs: ["market"] },
  { title: "Technical Explanation", field: "technical_analysis", inputs: ["technical"] },
  { title: "Fundamental Explanation", field: "fundamental_analysis", inputs: ["fundamental"] },
  { title: "Sentiment Explanation", field: "sentiment_analysis", inputs: ["news", "sentiment"] },
  { title: "Prediction Explanation", field: "prediction_analysis", inputs: ["prediction"] },
  { title: "Risk Explanation", field: "risk_analysis", inputs: ["risk"] },
  { title: "Decision Explanation", field: "decision_explanation", inputs: ["decision"] },
];

const INPUT_LABEL: Record<AiInputModule, string> = {
  market: "Market data",
  technical: "Technical analysis",
  fundamental: "Fundamental analysis",
  news: "News",
  sentiment: "Sentiment",
  prediction: "ML prediction",
  risk: "Risk",
  decision: "Decision",
};

const NOTE_BOX = "rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300";

function unavailableInputs(data: AiAnalysisResponse) {
  return (Object.keys(INPUT_LABEL) as AiInputModule[])
    .map((key) => ({ key, availability: data.data_availability[key] }))
    .filter((entry) => entry.availability !== undefined && !entry.availability.available);
}

/** Official Phase 14 result this explanation is about — shown from the stored snapshot, never from the AI text. */
function DecisionContext({ data }: { data: AiAnalysisResponse }) {
  const snap = data.decision_snapshot;
  return (
    <p className="text-xs text-slate-500 dark:text-slate-400" data-testid="ai-decision-context">
      {snap.decision ? (
        <>
          Explains the platform&apos;s Risk &amp; Decision result:{" "}
          <span className="font-semibold text-slate-700 dark:text-slate-200">{snap.decision}</span>
          {snap.risk_level && <> · Risk {RISK_LEVEL_LABEL[snap.risk_level] ?? snap.risk_level}</>}
          {snap.confidence !== null && <> · Confidence {Math.round(snap.confidence)}%</>}
          {snap.decision_score !== null && <> · Score {snap.decision_score > 0 ? "+" : ""}{Math.round(snap.decision_score)}</>}
        </>
      ) : (
        <>The platform&apos;s decision engine did not produce a BUY / HOLD / SELL result for this coin.</>
      )}
    </p>
  );
}

/** A successfully loaded, validated explanation. */
export function AiAnalysisContent({ data }: { data: AiAnalysisResponse }) {
  const { analysis } = data;
  const missing = unavailableInputs(data);

  return (
    <div className="space-y-4">
      {data.is_outdated && (
        <p role="note" className={NOTE_BOX}>
          The platform&apos;s decision has changed since this explanation was written, so it may describe an earlier result. Regenerate it to refresh.
        </p>
      )}
      {data.is_stale && !data.is_outdated && (
        <p role="note" className={NOTE_BOX}>
          This explanation has expired and may not reflect current conditions.
        </p>
      )}

      <div className="rounded-lg border border-sky-100 bg-sky-50/60 p-4 dark:border-sky-900/50 dark:bg-sky-950/20">
        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">AI Market Summary</h3>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-700 dark:text-slate-200">{analysis.summary}</p>
        <div className="mt-2">
          <DecisionContext data={data} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {SECTIONS.map((section) => {
          const gaps = section.inputs
            .map((key) => data.data_availability[key])
            .filter((a): a is NonNullable<typeof a> => a !== undefined && !a.available);
          return (
            <article key={section.field} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{section.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-700 dark:text-slate-200">{analysis[section.field]}</p>
              {gaps.length > 0 && (
                <p className="mt-2 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                  <span>Some input data was unavailable{gaps[0].reason ? `: ${gaps[0].reason}` : "."}</span>
                </p>
              )}
            </article>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <AiFactorList kind="bullish" items={analysis.bullish_factors} />
        <AiFactorList kind="bearish" items={analysis.bearish_factors} />
        <AiFactorList kind="risks" items={analysis.key_risks} />
        <AiFactorList kind="uncertainties" items={analysis.uncertainties} />
      </div>

      <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Data quality</h3>
        <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">{analysis.data_quality}</p>
        {missing.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs text-slate-500 dark:text-slate-400" aria-label="Inputs that were not available">
            {missing.map(({ key, availability }) => (
              <li key={key}>
                <span className="font-medium">{INPUT_LABEL[key]}:</span> {availability?.reason ?? "Not available."}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-xs text-slate-400" title={formatAbsoluteDateTime(data.generated_at)}>
        Generated {formatRelativeTime(data.generated_at)} · Model {data.model} · Prompt v{data.prompt_version}
        {data.cached ? " · Stored result" : " · Newly generated"}
      </p>
    </div>
  );
}
