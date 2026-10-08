import type { PredictionHorizon } from "../../types/predictions";
import { HORIZON_LABELS, HORIZON_LONG } from "../../utils/predictionDisplay";

interface HorizonSelectorProps {
  /** Only horizons that actually have a valid prediction are passed in. */
  horizons: PredictionHorizon[];
  value: PredictionHorizon;
  onChange: (horizon: PredictionHorizon) => void;
}

export function HorizonSelector({ horizons, value, onChange }: HorizonSelectorProps) {
  return (
    <div role="group" aria-label="Prediction horizon" className="flex rounded-lg border border-slate-200 p-0.5 dark:border-slate-700">
      {horizons.map((h) => (
        <button
          key={h}
          type="button"
          aria-pressed={value === h}
          aria-label={HORIZON_LONG[h]}
          onClick={() => onChange(h)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
            value === h
              ? "bg-slate-900 text-white dark:bg-sky-600"
              : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          }`}
        >
          {HORIZON_LABELS[h]}
        </button>
      ))}
    </div>
  );
}
