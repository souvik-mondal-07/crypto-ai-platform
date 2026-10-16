import type { EquityPoint } from "../../types/backtesting";
import { HEIGHT, PAD, WIDTH, buildChartPaths } from "../../utils/equityChart";
import { formatDay, formatUsd } from "../../utils/backtestFormat";

interface EquityCurveChartProps {
  strategy: EquityPoint[];
  benchmark: EquityPoint[];
}

/**
 * Equity curve of the simulated strategy against the benchmark, drawn ONLY from the points the API returned
 * (no smoothing, no padding with invented values). Plain SVG so it renders the same everywhere and in tests.
 */
export function EquityCurveChart({ strategy, benchmark }: EquityCurveChartProps) {
  if (strategy.length < 2) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Not enough points to draw an equity curve.</p>;
  }
  const paths = buildChartPaths(strategy, benchmark);
  if (!paths) return null;
  const label = `Equity curve with ${strategy.length} points from ${formatUsd(strategy[0].value)} to ${formatUsd(strategy[strategy.length - 1].value)}`;

  return (
    <figure>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={label}
        data-testid="equity-chart"
        className="h-auto w-full text-slate-400"
        preserveAspectRatio="xMidYMid meet"
      >
        <line x1={PAD.left} x2={WIDTH - PAD.right} y1={HEIGHT - PAD.bottom} y2={HEIGHT - PAD.bottom} stroke="currentColor" strokeOpacity="0.4" />
        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={HEIGHT - PAD.bottom} stroke="currentColor" strokeOpacity="0.4" />
        <text x={PAD.left - 6} y={PAD.top + 4} textAnchor="end" fontSize="11" fill="currentColor">{formatUsd(paths.maxV)}</text>
        <text x={PAD.left - 6} y={HEIGHT - PAD.bottom} textAnchor="end" fontSize="11" fill="currentColor">{formatUsd(paths.minV)}</text>
        <text x={PAD.left} y={HEIGHT - 8} textAnchor="start" fontSize="11" fill="currentColor">{formatDay(paths.startIso)}</text>
        <text x={WIDTH - PAD.right} y={HEIGHT - 8} textAnchor="end" fontSize="11" fill="currentColor">{formatDay(paths.endIso)}</text>
        {benchmark.length >= 2 && (
          <polyline data-testid="benchmark-line" data-points={benchmark.length} points={paths.benchmark} fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="5 4" />
        )}
        <polyline data-testid="strategy-line" data-points={strategy.length} points={paths.strategy} fill="none" stroke="#5b8cff" strokeWidth="2" />
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1.5"><span aria-hidden="true" className="inline-block h-0.5 w-5 bg-brand-500" />Strategy equity</span>
        {benchmark.length >= 2 && (
          <span className="flex items-center gap-1.5"><span aria-hidden="true" className="inline-block h-0.5 w-5 border-t-2 border-dashed border-slate-400" />Benchmark (equal-weight buy &amp; hold)</span>
        )}
      </figcaption>
    </figure>
  );
}
