import type { PredictionResponse } from "../../types/predictions";
import { changeColorClass, formatPercent, formatUsd } from "../../utils/formatters";
import { HORIZON_LONG } from "../../utils/predictionDisplay";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { ExpectedDirection } from "./ExpectedDirection";
import { ModelInformation } from "./ModelInformation";
import { PredictedRange } from "./PredictedRange";

const CARD = "rounded-lg border border-slate-200 p-3 dark:border-slate-700";
const LABEL = "mb-1 text-xs text-slate-500 dark:text-slate-400";

export function PredictionSummary({ p }: { p: PredictionResponse }) {
  return (
    <div>
      {p.is_stale && (
        <p role="note" className="mb-3 rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
          This prediction has expired and may no longer reflect current conditions.
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className={CARD}>
          <p className={LABEL}>Expected direction ({HORIZON_LONG[p.horizon]})</p>
          <ExpectedDirection direction={p.direction} />
          <p className={`mt-2 text-lg font-semibold ${changeColorClass(p.predicted_return)}`}>
            {formatPercent(p.predicted_return * 100)}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">predicted return from {formatUsd(p.current_price)}</p>
        </div>
        <div className={CARD}>
          <p className={LABEL}>Predicted price range</p>
          <PredictedRange p={p} />
        </div>
        <div className={CARD}>
          <p className={LABEL}>Confidence</p>
          <ConfidenceMeter p={p} />
        </div>
      </div>
      <div className="mt-4">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Model information</h3>
        <ModelInformation p={p} />
      </div>
    </div>
  );
}
