import type { DecisionResponse } from "../../types/decisions";
import { formatWholeNumber, riskScoreTone, TONE_BAR } from "../../utils/decisionDisplay";

/**
 * "How this was calculated": the rule-based explanation, any override that changed the outcome and
 * the weighted risk components. Collapsed by default so the headline stays compact.
 */
export function DecisionDetails({ data }: { data: DecisionResponse }) {
  const components = data.risk.components;
  return (
    <details className="mt-4 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        How this was calculated
      </summary>

      {data.explanation.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-slate-700 dark:text-slate-200">
          {data.explanation.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}

      {components.length > 0 && (
        <div className="mt-4">
          <h4 className="mb-2 text-xs font-semibold text-slate-600 dark:text-slate-300">Risk components</h4>
          <ul className="space-y-2">
            {components.map((c) => (
              <li key={c.key}>
                <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-300">
                  <span>
                    {c.label} <span className="text-slate-400">({formatWholeNumber(c.weight * 100)}% weight)</span>
                  </span>
                  <span>{c.available && c.score !== null ? `${formatWholeNumber(c.score)}/100` : "Not used"}</span>
                </div>
                {c.available && c.score !== null ? (
                  <div className="mt-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
                    <div
                      className={`h-1.5 rounded-full ${TONE_BAR[riskScoreTone(c.score)]}`}
                      style={{ width: `${Math.max(0, Math.min(100, c.score))}%` }}
                    />
                  </div>
                ) : (
                  c.reason && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{c.reason}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-4 text-xs text-slate-400">
        Engine v{data.engine_version} · risk configuration v{data.risk_config_version}
      </p>
    </details>
  );
}
