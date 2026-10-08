import { PREDICTION_DISCLAIMER } from "../../utils/predictionDisplay";

export function PredictionDisclaimer() {
  return (
    <p className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
      {PREDICTION_DISCLAIMER}
    </p>
  );
}
