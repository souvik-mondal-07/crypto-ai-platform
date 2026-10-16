import type { ReactNode } from "react";

import { AccuracySection } from "../../components/backtesting/AccuracySection";
import { BacktestForm } from "../../components/backtesting/BacktestForm";
import { BacktestResults } from "../../components/backtesting/BacktestResults";
import { DecisionEvaluationSection } from "../../components/backtesting/DecisionEvaluationSection";
import { RunsList } from "../../components/backtesting/RunsList";
import { RetryError } from "../../components/common/RetryError";
import { Loader } from "../../components/common/Loader";
import { AppShell } from "../../components/layout/AppShell";
import { PageHeader } from "../../components/ui/PageHeader";
import { useBacktestConfig, useBacktests } from "../../hooks/useBacktests";
import { useDecisionEvaluation, useModelAccuracy } from "../../hooks/useModelAccuracy";

function Section({ id, title, description, children }: { id: string; title: string; description?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="mt-8">
      <h2 id={id} className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
      {description && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** /backtesting — how well past predictions and decisions did, and a cost-aware historical simulation. Never trades. */
export function Backtesting() {
  const accuracy = useModelAccuracy();
  const decisions = useDecisionEvaluation();
  const { config, error: configError, retry: retryConfig } = useBacktestConfig();
  const backtests = useBacktests();

  return (
    <AppShell>
      <PageHeader
        title="Backtesting & Model Accuracy"
        subtitle="Historical evaluation and simulation only. No real trades are placed, and past results do not guarantee future performance."
      />

      <Section id="model-accuracy" title="Model Accuracy" description="Matured predictions compared with the actual market price at their horizon. Unmatured predictions are never counted as wrong.">
        <AccuracySection
          data={accuracy.data}
          loading={accuracy.loading}
          error={accuracy.error}
          filters={accuracy.filters}
          onFilters={accuracy.changeFilters}
          onRetry={accuracy.retry}
          refresh={accuracy.refresh}
          onRefresh={() => void accuracy.startRefresh()}
        />
      </Section>

      <Section id="decision-evaluation" title="Decision Evaluation" description="Stored BUY / HOLD / SELL decisions compared with the return that followed.">
        <DecisionEvaluationSection
          data={decisions.data}
          loading={decisions.loading}
          error={decisions.error}
          horizon={decisions.horizon}
          onHorizon={decisions.setHorizon}
          onRetry={decisions.retry}
        />
      </Section>

      <Section id="backtest-configuration" title="Backtest Configuration" description="Replays the stored Phase 14 decisions over real historical candles, with the costs you set below.">
        {configError ? (
          <RetryError message={configError} onRetry={retryConfig} />
        ) : config === null ? (
          <Loader label="Loading backtest options..." />
        ) : (
          <BacktestForm config={config} submitting={backtests.submitting} submitError={backtests.submitError} onSubmit={backtests.submit} />
        )}
      </Section>

      <Section id="backtest-results" title="Backtest Results">
        <div className="grid gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <div>
            <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">Recent runs</h3>
            <RunsList
              runs={backtests.runs}
              loading={backtests.runsLoading}
              error={backtests.runsError}
              selectedId={backtests.selectedId}
              onSelect={backtests.select}
              onRetry={backtests.retryRuns}
            />
          </div>
          <div className="min-w-0">
            <BacktestResults
              detail={backtests.detail}
              loading={backtests.detailLoading}
              error={backtests.detailError}
              onRetry={backtests.retryDetail}
              trades={backtests.trades}
              tradesError={backtests.tradesError}
              onTradesPage={backtests.setTradesPage}
            />
          </div>
        </div>
      </Section>
    </AppShell>
  );
}
