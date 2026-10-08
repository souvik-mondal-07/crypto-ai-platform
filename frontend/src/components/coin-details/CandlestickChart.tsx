import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";

import { useTheme } from "../../context/ThemeContext";
import { toCandlestickData, toSmaOverlayData } from "../../utils/chartUtils";
import type { HistoricalCandle } from "../../types/market";

interface CandlestickChartProps {
  candles: HistoricalCandle[];
  height?: number;
  /** Overlays SMA20/SMA50 lines computed client-side from `candles` (Phase 10). Off by default so the chart stays exactly as before unless a caller opts in. */
  showMovingAverages?: boolean;
}

/** Stable module-level constant — identity never changes across renders, so the overlay effect below only re-runs when `candles`/`showMovingAverages` actually change, not on every parent re-render. */
const MOVING_AVERAGE_OVERLAYS: { period: number; color: string; label: string }[] = [
  { period: 20, color: "#f59e0b", label: "SMA 20" }, // amber
  { period: 50, color: "#8b5cf6", label: "SMA 50" }, // violet
];

const LIGHT_THEME = {
  background: "#ffffff",
  textColor: "#475569",
  gridColor: "#f1f5f9",
  borderColor: "#e2e8f0",
};

const DARK_THEME = {
  background: "#0f172a",
  textColor: "#cbd5e1",
  gridColor: "#1e293b",
  borderColor: "#334155",
};

/**
 * Candlestick price chart. Zoom/pan/crosshair come from the library.
 * An optional SMA20/SMA50 overlay (Phase 10) can be toggled on via
 * `showMovingAverages` — off by default, so existing callers are
 * unaffected. Full technical-indicator panels (RSI, MACD, Bollinger
 * Bands, etc.) live in the separate Technical Analysis section below
 * this chart, not as chart overlays — those are non-price-scale
 * values that don't belong on a price chart's axis.
 *
 * The chart instance is created once and then *updated* on data/theme
 * changes rather than recreated, and is always removed on unmount so
 * the library's internal listeners don't leak.
 */
export function CandlestickChart({ candles, height = 400, showMovingAverages = false }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const maSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const { theme } = useTheme();

  // Create the chart once, and tear it down on unmount.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: LIGHT_THEME.textColor,
      },
      rightPriceScale: { borderColor: LIGHT_THEME.borderColor },
      timeScale: { borderColor: LIGHT_THEME.borderColor, timeVisible: true },
      crosshair: { mode: 1 },
      handleScroll: true,
      handleScale: true,
    });

    const series = chart.addCandlestickSeries({
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderUpColor: "#16a34a",
      borderDownColor: "#dc2626",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
    });

    // Moving-average overlay lines — created once (like the
    // candlestick series itself), hidden by default via empty data
    // until an effect below decides whether to populate them.
    maSeriesRef.current = MOVING_AVERAGE_OVERLAYS.map((overlay) =>
      chart.addLineSeries({
        color: overlay.color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: overlay.label,
      })
    );

    chartRef.current = chart;
    seriesRef.current = series;

    // Responsive resizing — ResizeObserver rather than a window
    // listener so the chart also reacts to layout changes that don't
    // resize the window (sidebar toggles, etc.).
    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      maSeriesRef.current = [];
    };
  }, [height]);

  // Feed data whenever the candles change (e.g. timeframe switch).
  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;

    series.setData(toCandlestickData(candles));
    chart.timeScale().fitContent();
  }, [candles]);

  // Populate (or clear) the moving-average overlay lines. Kept as its
  // own effect so toggling `showMovingAverages` doesn't touch the
  // candlestick series at all — the existing chart/timeframe
  // behavior is untouched either way.
  useEffect(() => {
    if (maSeriesRef.current.length === 0) return;
    MOVING_AVERAGE_OVERLAYS.forEach((overlay, index) => {
      const lineSeries = maSeriesRef.current[index];
      lineSeries.setData(showMovingAverages ? toSmaOverlayData(candles, overlay.period) : []);
    });
  }, [candles, showMovingAverages]);

  // Re-style on theme change, without recreating the chart.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const palette = theme === "dark" ? DARK_THEME : LIGHT_THEME;
    chart.applyOptions({
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: palette.textColor,
      },
      grid: {
        vertLines: { color: palette.gridColor },
        horzLines: { color: palette.gridColor },
      },
      rightPriceScale: { borderColor: palette.borderColor },
      timeScale: { borderColor: palette.borderColor },
    });
  }, [theme]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Candlestick price chart"
      className="w-full"
      style={{ height }}
    />
  );
}
