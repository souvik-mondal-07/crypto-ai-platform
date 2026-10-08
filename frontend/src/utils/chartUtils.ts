import type { CandlestickData, LineData, UTCTimestamp } from "lightweight-charts";

import type { HistoricalCandle } from "../types/market";

/**
 * Converts backend candles into Lightweight Charts' expected shape.
 *
 * The library wants `time` as a UTC timestamp in **seconds**; the
 * backend sends an ISO-8601 string. Rows whose timestamp can't be
 * parsed are dropped rather than passed through as NaN — a NaN time
 * makes the chart silently render nothing, which is much harder to
 * diagnose than a missing candle.
 *
 * The backend already validates OHLC consistency and sorts
 * chronologically (see backend/app/providers/coingecko/mapper.py), so
 * this function does not re-validate or re-sort the values themselves
 * — but it does de-duplicate identical timestamps, which Lightweight
 * Charts rejects outright.
 */
export function toCandlestickData(candles: HistoricalCandle[]): CandlestickData[] {
  const result: CandlestickData[] = [];
  let previousTime: number | null = null;

  for (const candle of candles) {
    const parsedMs = Date.parse(candle.timestamp);
    if (Number.isNaN(parsedMs)) continue;

    const timeSeconds = Math.floor(parsedMs / 1000);

    // Lightweight Charts requires strictly ascending, unique times.
    if (previousTime !== null && timeSeconds <= previousTime) continue;
    previousTime = timeSeconds;

    result.push({
      time: timeSeconds as UTCTimestamp,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    });
  }

  return result;
}

/**
 * Simple moving average of candle closes, expressed as Lightweight
 * Charts line data aligned to the same timestamps as the candlestick
 * series. Computed client-side from the same real candles already
 * loaded for the chart — not a separate/fabricated data source, and
 * not the backend's cached single-value SMA (that value is the
 * *current* SMA shown in the Technical Analysis section; this is the
 * full rolling series needed to draw a line across the whole chart).
 *
 * Points before there's enough history for the period are omitted
 * entirely (never a zero/guessed value plotted on the chart).
 */
export function toSmaOverlayData(candles: HistoricalCandle[], period: number): LineData[] {
  if (period <= 0 || candles.length < period) return [];

  const converted = toCandlestickData(candles);
  const result: LineData[] = [];
  let windowSum = 0;

  for (let i = 0; i < converted.length; i++) {
    windowSum += converted[i].close;
    if (i >= period) {
      windowSum -= converted[i - period].close;
    }
    if (i >= period - 1) {
      result.push({ time: converted[i].time, value: windowSum / period });
    }
  }

  return result;
}

/**
 * Close-price line for the Dashboard performance chart, from the SAME real
 * backend candles the Coin Details chart uses. Reuses `toCandlestickData` so
 * timestamp parsing / de-duplication stay in one place.
 */
export function toCloseLineData(candles: HistoricalCandle[]): LineData[] {
  return toCandlestickData(candles).map((point) => ({ time: point.time, value: point.close }));
}

/**
 * Percentage change across a candle series: first candle's open to last
 * candle's close. `null` when there are no candles or the starting price is
 * not positive — never a fabricated 0%.
 */
export function periodChangePercent(candles: HistoricalCandle[]): number | null {
  const points = toCandlestickData(candles);
  if (points.length === 0) return null;
  const start = points[0].open;
  const end = points[points.length - 1].close;
  if (!(start > 0)) return null;
  return ((end - start) / start) * 100;
}
