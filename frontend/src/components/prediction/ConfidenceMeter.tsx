import type { PredictionResponse } from "../../types/predictions";
import { formatPlainPercent } from "../../utils/formatters";

export function ConfidenceMeter({ p }: { p: PredictionResponse }) {
  if (p.confidence === null || p.confidence_status === "unavailable") {
    return (
      <div>
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Unavailable</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {p.confidence_note ?? "A reliable confidence could not be calculated for this prediction."}
        </p>
      </div>
    );
  }
  const pct = Math.round(p.confidence * 100);
  return (
    <div>
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{formatPlainPercent(p.confidence * 100, 0)}</p>
      <div
        role="meter"
        aria-label="Direction confidence"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="mt-2 h-2 rounded-full bg-slate-100 dark:bg-slate-800"
      >
        <div className="h-2 rounded-full bg-sky-500 dark:bg-sky-400" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        Calibrated on held-out history: how often predictions of this strength got the direction right. It is not the chance of reaching a price.
      </p>
    </div>
  );
}
