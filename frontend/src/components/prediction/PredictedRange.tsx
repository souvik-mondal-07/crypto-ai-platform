import type { PredictionResponse } from "../../types/predictions";
import { formatPercent, formatPlainPercent, formatUsd } from "../../utils/formatters";
import { markerPosition } from "../../utils/predictionDisplay";

export function PredictedRange({ p }: { p: PredictionResponse }) {
  const price = p.predicted_price_range;
  const ret = p.predicted_return_range;
  if (!price || !ret) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        A predicted range is not available for this model (not enough validation data to calibrate one).
      </p>
    );
  }
  const lo = Math.min(price.lower, p.current_price);
  const hi = Math.max(price.upper, p.current_price);
  const span = hi - lo || 1;
  const left = ((price.lower - lo) / span) * 100;
  const width = ((price.upper - price.lower) / span) * 100;
  const marker = markerPosition(p.current_price, price.lower, price.upper);
  const measured = p.evaluation?.interval_coverage_test;

  return (
    <div>
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        {formatUsd(price.lower)} – {formatUsd(price.upper)}
      </p>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        {formatPercent(ret.lower * 100)} to {formatPercent(ret.upper * 100)} from the current price
      </p>
      <div
        role="img"
        aria-label={`Predicted price range ${formatUsd(price.lower)} to ${formatUsd(price.upper)}; current price ${formatUsd(p.current_price)}`}
        className="relative mt-3 h-3 rounded-full bg-slate-100 dark:bg-slate-800"
      >
        <div className="absolute top-0 h-3 rounded-full bg-sky-300 dark:bg-sky-700" style={{ left: `${left}%`, width: `${width}%` }} />
        <div className="absolute -top-1 h-5 w-0.5 bg-slate-900 dark:bg-slate-100" style={{ left: `${marker}%` }} title="Current price" />
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        Marker = price at the start of the forecast ({formatUsd(p.current_price)}).
        {p.range_nominal_coverage !== null && (
          <>
            {" "}Designed to contain about {formatPlainPercent(p.range_nominal_coverage * 100, 0)} of outcomes
            {measured !== null && measured !== undefined ? `; it contained ${formatPlainPercent(measured * 100, 0)} on held-out data` : ""}.
          </>
        )}
      </p>
    </div>
  );
}
