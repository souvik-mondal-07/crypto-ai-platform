import { TIMEFRAMES, type Timeframe } from "../../types/market";

interface TimeframeSelectorProps {
  value: Timeframe;
  onChange: (timeframe: Timeframe) => void;
  disabled?: boolean;
}

/** Only renders timeframes the backend actually supports (see types/market.ts). */
export function TimeframeSelector({ value, onChange, disabled = false }: TimeframeSelectorProps) {
  return (
    <div
      role="group"
      aria-label="Select chart timeframe"
      className="flex gap-1 rounded-lg border border-slate-200 p-0.5 dark:border-slate-700"
    >
      {TIMEFRAMES.map((timeframe) => {
        const isSelected = timeframe === value;
        return (
          <button
            key={timeframe}
            type="button"
            onClick={() => onChange(timeframe)}
            disabled={disabled}
            aria-pressed={isSelected}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              isSelected
                ? "bg-slate-900 text-white dark:bg-sky-600"
                : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800"
            }`}
          >
            {timeframe}
          </button>
        );
      })}
    </div>
  );
}
