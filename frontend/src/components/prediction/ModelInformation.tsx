import type { PredictionResponse } from "../../types/predictions";
import { formatAbsoluteDateTime, formatPlainPercent, formatRelativeTime } from "../../utils/formatters";
import { modelDisplayName } from "../../utils/predictionDisplay";

export function ModelInformation({ p }: { p: PredictionResponse }) {
  const ev = p.evaluation;
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
      <div>
        <dt className="text-xs text-slate-500 dark:text-slate-400">Model</dt>
        <dd className="font-medium text-slate-900 dark:text-slate-100">{modelDisplayName(p.model)}</dd>
      </div>
      <div>
        <dt className="text-xs text-slate-500 dark:text-slate-400">Model version</dt>
        <dd className="font-medium text-slate-900 dark:text-slate-100">{p.model_version}</dd>
      </div>
      <div>
        <dt className="text-xs text-slate-500 dark:text-slate-400">Generated</dt>
        <dd className="font-medium text-slate-900 dark:text-slate-100" title={formatAbsoluteDateTime(p.generated_at)}>
          {formatRelativeTime(p.generated_at)}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-slate-500 dark:text-slate-400">Based on candle closing</dt>
        <dd className="font-medium text-slate-900 dark:text-slate-100">{formatAbsoluteDateTime(p.reference_time)}</dd>
      </div>
      <div>
        <dt className="text-xs text-slate-500 dark:text-slate-400">Forecast target time</dt>
        <dd className="font-medium text-slate-900 dark:text-slate-100">{formatAbsoluteDateTime(p.target_time)}</dd>
      </div>
      {ev && ev.test_directional_accuracy !== null && (
        <div>
          <dt className="text-xs text-slate-500 dark:text-slate-400">Held-out direction accuracy</dt>
          <dd className="font-medium text-slate-900 dark:text-slate-100">
            {formatPlainPercent(ev.test_directional_accuracy * 100, 1)}
            {ev.test_samples ? <span className="text-xs font-normal text-slate-500 dark:text-slate-400"> ({ev.test_samples} samples)</span> : null}
          </dd>
        </div>
      )}
    </dl>
  );
}
