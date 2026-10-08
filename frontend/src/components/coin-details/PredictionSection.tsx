import { useState } from "react";

import { useCoinPredictions } from "../../hooks/useCoinPredictions";
import type { PredictionHorizon } from "../../types/predictions";
import { chooseHorizon, describeUnavailable } from "../../utils/predictionDisplay";
import { EmptyState } from "../common/EmptyState";
import { RetryError } from "../common/RetryError";
import { HorizonSelector } from "../prediction/HorizonSelector";
import { PredictionDisclaimer } from "../prediction/PredictionDisclaimer";
import { PredictionSkeleton } from "../prediction/PredictionSkeleton";
import { PredictionSummary } from "../prediction/PredictionSummary";

/**
 * Model Prediction (Phase 13). Shows range/probability-style ML estimates for the
 * horizons that have a valid model + enough real history, nothing else. It is not
 * advice or a recommendation and says so on screen.
 */
export function PredictionSection({ coinId }: { coinId: string }) {
  const { data, loading, error, retry } = useCoinPredictions(coinId);
  const [selected, setSelected] = useState<PredictionHorizon | null>(null);

  const available = data?.predictions.map((p) => p.horizon) ?? [];
  const horizon = chooseHorizon(selected, available);
  const current = data?.predictions.find((p) => p.horizon === horizon) ?? null;
  const unavailable = data && data.predictions.length === 0 ? describeUnavailable(data) : null;

  return (
    <section
      aria-labelledby="coin-prediction-heading"
      className="mt-6 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="coin-prediction-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Model Prediction
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">Machine-learning estimate from historical market data</p>
        </div>
        {horizon && <HorizonSelector horizons={available} value={horizon} onChange={setSelected} />}
      </div>

      {loading && <PredictionSkeleton />}
      {error && <RetryError message={error.message} onRetry={retry} />}
      {unavailable && (
        <div className="space-y-1">
          <EmptyState message={unavailable.title} />
          <p className="text-xs text-slate-500 dark:text-slate-400">{unavailable.reason}</p>
        </div>
      )}
      {current && <PredictionSummary p={current} />}

      <PredictionDisclaimer />
    </section>
  );
}
