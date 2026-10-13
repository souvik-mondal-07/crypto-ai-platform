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
      className="segmented flex-wrap"
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
            className={`segmented-item ${isSelected ? "segmented-item-active" : ""}`}
          >
            {timeframe}
          </button>
        );
      })}
    </div>
  );
}
