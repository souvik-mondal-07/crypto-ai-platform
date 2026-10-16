import type { EquityPoint } from "../types/backtesting";

export const WIDTH = 800;
export const HEIGHT = 280;
export const PAD = { left: 64, right: 16, top: 16, bottom: 28 };

/** Maps the API's points to SVG coordinates on a shared time axis and value axis. */
export function buildChartPaths(strategy: EquityPoint[], benchmark: EquityPoint[]) {
  const all = [...strategy, ...benchmark];
  const times = all.map((point) => new Date(point.time).getTime()).filter(Number.isFinite);
  const values = all.map((point) => point.value).filter(Number.isFinite);
  if (times.length === 0 || values.length === 0) return null;
  const minT = Math.min(...times);
  const maxT = Math.max(...times);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const spanT = maxT - minT || 1;
  const spanV = maxV - minV || 1;
  const x = (iso: string) => PAD.left + ((new Date(iso).getTime() - minT) / spanT) * (WIDTH - PAD.left - PAD.right);
  const y = (value: number) => HEIGHT - PAD.bottom - ((value - minV) / spanV) * (HEIGHT - PAD.top - PAD.bottom);
  const toPoints = (series: EquityPoint[]) => series.map((point) => `${x(point.time).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ");
  return {
    strategy: toPoints(strategy),
    benchmark: toPoints(benchmark),
    minV,
    maxV,
    startIso: new Date(minT).toISOString(),
    endIso: new Date(maxT).toISOString(),
  };
}
