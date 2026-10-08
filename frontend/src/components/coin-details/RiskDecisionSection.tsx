import { RefreshCw } from "lucide-react";

import { useCoinDecision } from "../../hooks/useCoinDecision";
import type { DecisionResponse } from "../../types/decisions";
import {
  predictionMissingButDecided,
  PREDICTION_FALLBACK_NOTE,
  statusTitle,
  unusableInputs,
} from "../../utils/decisionDisplay";
import { formatAbsoluteDateTime, formatRelativeTime } from "../../utils/formatters";
import { DecisionBadge } from "../decision/DecisionBadge";
import { DecisionDetails } from "../decision/DecisionDetails";
import { DecisionDisclaimer } from "../decision/DecisionDisclaimer";
import { DecisionMetrics } from "../decision/DecisionMetrics";
import { DecisionSkeleton } from "../decision/DecisionSkeleton";
import { FactorList } from "../decision/FactorList";
import { SignalSummary } from "../decision/SignalSummary";
import { RetryError } from "../common/RetryError";

const NOTE_BOX = "rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300";
const NOTE = `mb-3 ${NOTE_BOX}`;

/** Why no decision was produced, with the inputs that could not be used. */
function NoDecision({ data }: { data: DecisionResponse }) {
  const inputs = unusableInputs(data);
  return (
    <div className="space-y-3">
      <div role="status" className="rounded-lg border border-dashed border-slate-300 p-4 dark:border-slate-700">
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{statusTitle(data.status)}</p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          {data.status_reason ?? "A decision cannot be calculated from the data that is currently available."}
        </p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          No decision is shown rather than guessing from incomplete data.
        </p>
      </div>
      {inputs.length > 0 && (
        <ul className="space-y-1 text-sm" aria-label="Inputs that could not be used">
          {inputs.map((input) => (
            <li key={input.key} className="text-slate-600 dark:text-slate-300">
              <span className="font-medium">{input.label}:</span> {input.reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Decision({ data }: { data: DecisionResponse }) {
  return (
    <div>
      {data.is_stale && (
        <p role="note" className={NOTE}>
          This decision has expired and may no longer reflect current conditions.
        </p>
      )}
      {predictionMissingButDecided(data) && (
        <p role="note" className={NOTE}>
          {PREDICTION_FALLBACK_NOTE}
        </p>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        {data.decision && <DecisionBadge decision={data.decision} />}
        <p className="text-xs text-slate-500 dark:text-slate-400">Model-based decision from the signals below</p>
      </div>

      <DecisionMetrics data={data} />

      {data.overrides.length > 0 && (
        <ul className={`mt-3 space-y-1 ${NOTE_BOX}`} aria-label="Risk rules applied">
          {data.overrides.map((o) => (
            <li key={o.rule}>{o.description}</li>
          ))}
        </ul>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <SignalSummary data={data} />
        <FactorList kind="positive" factors={data.positive_factors} />
        <FactorList kind="negative" factors={data.negative_factors} />
      </div>

      {data.warnings.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-slate-500 dark:text-slate-400" aria-label="Data notes">
          {data.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <DecisionDetails data={data} />
    </div>
  );
}

/**
 * Risk & Decision (Phase 14). Shows the backend's deterministic, rule-based BUY/HOLD/SELL with its
 * risk score/level, confidence, signals and factors. Loads independently of the other sections (own
 * loading / error / no-decision states) and never presents the result as a guaranteed signal.
 */
export function RiskDecisionSection({ coinId }: { coinId: string }) {
  const { data, loading, refreshing, error, retry, refresh } = useCoinDecision(coinId);

  return (
    <section
      aria-labelledby="coin-risk-decision-heading"
      className="mt-6 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="coin-risk-decision-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Risk &amp; Decision
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">Model-Based Decision</p>
        </div>
        {data && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400" title={formatAbsoluteDateTime(data.generated_at)}>
              Calculated {formatRelativeTime(data.generated_at)}
            </span>
            <button
              type="button"
              onClick={refresh}
              disabled={refreshing}
              aria-label="Recalculate risk and decision"
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
              Recalculate
            </button>
          </div>
        )}
      </div>

      {loading && <DecisionSkeleton />}
      {error && <RetryError message={error} onRetry={retry} />}
      {data && (data.decision === null ? <NoDecision data={data} /> : <Decision data={data} />)}

      <DecisionDisclaimer />
    </section>
  );
}
