import { useState, type ReactNode } from "react";
import { RefreshCw } from "lucide-react";

import { EmptyState } from "../common/EmptyState";
import { ErrorMessage } from "../common/ErrorMessage";
import { Loader } from "../common/Loader";
import { formatDecimal, formatRelativeTime, formatUsd } from "../../utils/formatters";
import type {
  MacdCrossover,
  RsiZone,
  TechnicalAnalysisResponse,
  TrendLabel,
} from "../../types/technicalAnalysis";

interface TechnicalAnalysisSectionProps {
  technicalAnalysis: TechnicalAnalysisResponse | null;
  loading: boolean;
  error: string | null;
  insufficientData: boolean;
  onRetry: () => void;
  showMovingAverageOverlay: boolean;
  onToggleMovingAverageOverlay: (next: boolean) => void;
}

const TREND_STYLES: Record<TrendLabel, string> = {
  bullish: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
  bearish: "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400",
  neutral: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

const RSI_ZONE_STYLES: Record<RsiZone, string> = {
  overbought: "text-rose-600 dark:text-rose-400",
  oversold: "text-emerald-600 dark:text-emerald-400",
  neutral: "text-slate-500 dark:text-slate-400",
};

const MACD_CROSSOVER_LABEL: Record<MacdCrossover, string> = {
  bullish_crossover: "Bullish crossover",
  bearish_crossover: "Bearish crossover",
  none: "No recent crossover",
};

function IndicatorCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
      {children}
    </div>
  );
}

/**
 * Technical Analysis section for the Coin Details page (Phase 10).
 *
 * Purely descriptive: RSI/MACD/moving averages/Bollinger Bands/ATR/
 * volume/support-resistance/trend are shown as-is from the backend,
 * with no BUY/HOLD/SELL framing anywhere — that decision layer is a
 * later phase and deliberately out of scope here. Every field that
 * the backend returned `null` (not enough history for that period,
 * or volume data was never synced) renders "N/A"/"—", never a
 * fabricated value.
 */
export function TechnicalAnalysisSection({
  technicalAnalysis,
  loading,
  error,
  insufficientData,
  onRetry,
  showMovingAverageOverlay,
  onToggleMovingAverageOverlay,
}: TechnicalAnalysisSectionProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Technical Analysis</h2>
          {technicalAnalysis && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${TREND_STYLES[technicalAnalysis.trend.trend]}`}
            >
              {technicalAnalysis.trend.trend}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {technicalAnalysis && (
            <label className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <input
                type="checkbox"
                checked={showMovingAverageOverlay}
                onChange={(e) => onToggleMovingAverageOverlay(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-slate-600"
              />
              Show SMA 20/50 on chart
            </label>
          )}
          <button
            type="button"
            onClick={onRetry}
            disabled={loading}
            className="flex items-center gap-1 text-xs font-medium text-sky-600 hover:underline disabled:opacity-50 dark:text-sky-400"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-xs font-medium text-slate-500 hover:underline dark:text-slate-400"
          >
            {expanded ? "Collapse" : "Expand"}
          </button>
        </div>
      </div>

      {!expanded ? null : loading ? (
        <div className="flex h-[160px] items-center justify-center">
          <Loader label="Computing technical analysis..." />
        </div>
      ) : error && insufficientData ? (
        <EmptyState message="Not enough historical data yet to compute technical analysis for this timeframe." />
      ) : error ? (
        <div className="flex flex-col items-center gap-2 py-6">
          <ErrorMessage message={error} />
          <button
            type="button"
            onClick={onRetry}
            className="text-sm font-medium text-sky-600 hover:underline dark:text-sky-400"
          >
            Retry
          </button>
        </div>
      ) : !technicalAnalysis ? (
        <EmptyState message="Technical analysis is not available for this coin yet." />
      ) : (
        <>
          <p className="mb-3 text-xs text-slate-400">
            Based on {technicalAnalysis.candle_count} real historical candles ({technicalAnalysis.timeframe}) via{" "}
            {technicalAnalysis.data_source} · calculated {formatRelativeTime(technicalAnalysis.calculated_at)}. For
            informational purposes only — not investment advice.
          </p>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <IndicatorCard title="RSI">
              <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {formatDecimal(technicalAnalysis.rsi.current, 1)}
              </p>
              {technicalAnalysis.rsi.zone && (
                <p className={`mt-0.5 text-xs font-medium capitalize ${RSI_ZONE_STYLES[technicalAnalysis.rsi.zone]}`}>
                  {technicalAnalysis.rsi.zone}
                </p>
              )}
              <p className="mt-1 text-xs text-slate-400">{technicalAnalysis.rsi.period}-period</p>
            </IndicatorCard>

            <IndicatorCard title="MACD">
              <dl className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <dt className="text-xs text-slate-400">MACD</dt>
                  <dd className="font-semibold text-slate-900 dark:text-slate-100">
                    {formatDecimal(technicalAnalysis.macd.current.macd)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-400">Signal</dt>
                  <dd className="font-semibold text-slate-900 dark:text-slate-100">
                    {formatDecimal(technicalAnalysis.macd.current.signal)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-400">Histogram</dt>
                  <dd className="font-semibold text-slate-900 dark:text-slate-100">
                    {formatDecimal(technicalAnalysis.macd.current.histogram)}
                  </dd>
                </div>
              </dl>
              <p className="mt-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                {MACD_CROSSOVER_LABEL[technicalAnalysis.macd.crossover]}
              </p>
            </IndicatorCard>

            <IndicatorCard title="Moving Averages">
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-sm">
                {Object.entries(technicalAnalysis.moving_averages.sma).map(([period, value]) => (
                  <div key={`sma-${period}`} className="flex justify-between">
                    <dt className="text-slate-400">SMA {period}</dt>
                    <dd className="font-medium text-slate-900 dark:text-slate-100">{formatUsd(value)}</dd>
                  </div>
                ))}
                {Object.entries(technicalAnalysis.moving_averages.ema).map(([period, value]) => (
                  <div key={`ema-${period}`} className="flex justify-between">
                    <dt className="text-slate-400">EMA {period}</dt>
                    <dd className="font-medium text-slate-900 dark:text-slate-100">{formatUsd(value)}</dd>
                  </div>
                ))}
              </dl>
            </IndicatorCard>

            <IndicatorCard title="Bollinger Bands">
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-400">Upper</dt>
                  <dd className="font-medium text-slate-900 dark:text-slate-100">
                    {formatUsd(technicalAnalysis.bollinger_bands.upper)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-400">Middle</dt>
                  <dd className="font-medium text-slate-900 dark:text-slate-100">
                    {formatUsd(technicalAnalysis.bollinger_bands.middle)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-400">Lower</dt>
                  <dd className="font-medium text-slate-900 dark:text-slate-100">
                    {formatUsd(technicalAnalysis.bollinger_bands.lower)}
                  </dd>
                </div>
              </dl>
              <p className="mt-1 text-xs text-slate-400">
                {technicalAnalysis.bollinger_bands.period}-period, {technicalAnalysis.bollinger_bands.num_std_dev}σ
              </p>
            </IndicatorCard>

            <IndicatorCard title="ATR">
              <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {formatUsd(technicalAnalysis.atr.current)}
              </p>
              <p className="mt-1 text-xs text-slate-400">{technicalAnalysis.atr.period}-period average true range</p>
            </IndicatorCard>

            <IndicatorCard title="Volume Analysis">
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Current 24h volume (USD)</dt><dd className="font-medium">{formatUsd(technicalAnalysis.volume.current_volume_24h_usd)}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Recent average (base asset)</dt><dd className="font-medium">{technicalAnalysis.volume.average_volume === null ? "N/A" : formatDecimal(technicalAnalysis.volume.average_volume)}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Volume change</dt><dd className="font-medium">{technicalAnalysis.volume.volume_change_percent === null ? "N/A" : `${formatDecimal(technicalAnalysis.volume.volume_change_percent)}%`}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Trend</dt><dd className="font-medium capitalize">{technicalAnalysis.volume.trend}</dd></div>
              </dl>
              <p className="mt-2 text-xs text-slate-400">
                {technicalAnalysis.volume.historical_volume.length === 0 ? "Historical volume unavailable" : `${technicalAnalysis.volume.historical_volume.length} real ${technicalAnalysis.volume.historical_volume_source ?? "provider"} historical candles; volumes are in base-asset units.`}
              </p>
              {technicalAnalysis.volume.historical_volume.length > 0 && (
                <ol className="mt-2 max-h-32 space-y-1 overflow-y-auto border-t border-slate-100 pt-2 text-xs dark:border-slate-800" aria-label="Recent historical volume">
                  {technicalAnalysis.volume.historical_volume.slice(-5).reverse().map((point) => (
                    <li key={point.timestamp} className="flex justify-between gap-2 text-slate-500 dark:text-slate-400">
                      <time dateTime={point.timestamp}>{new Date(point.timestamp).toLocaleString()}</time>
                      <span className="font-medium text-slate-800 dark:text-slate-200">{formatDecimal(point.volume)}</span>
                    </li>
                  ))}
                </ol>
              )}
            </IndicatorCard>

            <IndicatorCard title="Support / Resistance">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="mb-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">Support</p>
                  {technicalAnalysis.support_resistance.support_levels.length === 0 ? (
                    <p className="text-xs text-slate-400">N/A</p>
                  ) : (
                    <ul className="space-y-0.5">
                      {technicalAnalysis.support_resistance.support_levels.map((level) => (
                        <li key={level} className="font-medium text-slate-900 dark:text-slate-100">
                          {formatUsd(level)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-rose-600 dark:text-rose-400">Resistance</p>
                  {technicalAnalysis.support_resistance.resistance_levels.length === 0 ? (
                    <p className="text-xs text-slate-400">N/A</p>
                  ) : (
                    <ul className="space-y-0.5">
                      {technicalAnalysis.support_resistance.resistance_levels.map((level) => (
                        <li key={level} className="font-medium text-slate-900 dark:text-slate-100">
                          {formatUsd(level)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
              <p className="mt-2 text-xs text-slate-400">
                Approximate levels based on recent swing points — not guaranteed to hold.
              </p>
            </IndicatorCard>
          </div>
        </>
      )}
    </div>
  );
}
