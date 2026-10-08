import { useEffect, useRef, useState } from "react";
import { ColorType, createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";

import { useTheme } from "../../context/ThemeContext";
import { toCloseLineData } from "../../utils/chartUtils";
import { formatUsd } from "../../utils/formatters";
import type { HistoricalCandle } from "../../types/market";

interface PerformanceChartProps {
  candles: HistoricalCandle[];
  /** Colours the line green/red from the real period change. */
  positive: boolean;
  height?: number;
  ariaLabel: string;
}

const PALETTE = {
  light: { text: "#475569", grid: "#f1f5f9", border: "#e2e8f0" },
  dark: { text: "#cbd5e1", grid: "#1e293b", border: "#334155" },
};

const UP = { line: "#16a34a", top: "rgba(22,163,74,0.25)", bottom: "rgba(22,163,74,0)" };
const DOWN = { line: "#dc2626", top: "rgba(220,38,38,0.25)", bottom: "rgba(220,38,38,0)" };

interface Hover {
  x: number;
  value: number;
  time: number;
}

/**
 * Close-price area chart for the Dashboard performance section. Same
 * lifecycle rules as CandlestickChart: created once, updated on data/theme
 * change, always removed on unmount. Crosshair tooltip shows the real price
 * and timestamp under the cursor.
 */
export function PerformanceChart({ candles, positive, height = 320, ariaLabel }: PerformanceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const { theme } = useTheme();
  const [hover, setHover] = useState<Hover | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: PALETTE.light.text },
      rightPriceScale: { borderColor: PALETTE.light.border },
      timeScale: { borderColor: PALETTE.light.border, timeVisible: true },
      crosshair: { mode: 1 },
    });
    const series = chart.addAreaSeries({
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      lineColor: UP.line,
      topColor: UP.top,
      bottomColor: UP.bottom,
    });

    chart.subscribeCrosshairMove((param) => {
      const data = param.seriesData.get(series) as { value?: number } | undefined;
      if (!param.point || typeof param.time !== "number" || !data || typeof data.value !== "number") {
        setHover(null);
        return;
      }
      setHover({ x: param.point.x, value: data.value, time: param.time });
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) chart.applyOptions({ width: entry.contentRect.width });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;
    series.setData(toCloseLineData(candles));
    chart.timeScale().fitContent();
  }, [candles]);

  useEffect(() => {
    const colors = positive ? UP : DOWN;
    seriesRef.current?.applyOptions({ lineColor: colors.line, topColor: colors.top, bottomColor: colors.bottom });
  }, [positive]);

  useEffect(() => {
    const palette = theme === "dark" ? PALETTE.dark : PALETTE.light;
    chartRef.current?.applyOptions({
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: palette.text },
      grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
      rightPriceScale: { borderColor: palette.border },
      timeScale: { borderColor: palette.border },
    });
  }, [theme]);

  return (
    <div className="relative">
      <div ref={containerRef} role="img" aria-label={ariaLabel} className="w-full" style={{ height }} />
      {hover && (
        <div
          className="pointer-events-none absolute top-2 z-10 rounded-md border border-slate-200 bg-white/95 px-2 py-1 text-xs shadow-sm dark:border-slate-700 dark:bg-slate-900/95"
          style={{ left: Math.min(Math.max(hover.x + 12, 0), Math.max((containerRef.current?.clientWidth ?? 0) - 150, 0)) }}
        >
          <p className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{formatUsd(hover.value)}</p>
          <p className="text-slate-500 dark:text-slate-400">
            {new Date(hover.time * 1000).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}
          </p>
        </div>
      )}
    </div>
  );
}
