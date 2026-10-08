import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { EmptyState } from "../common/EmptyState";
import { RetryError } from "../common/RetryError";
import { SectionHeading } from "../common/SectionHeading";
import { formatCompactUsd, formatPercent, formatUsd } from "../../utils/formatters";
import { squarify } from "../../utils/treemap";
import type { MarketCoin } from "../../types/market";

interface MarketHeatmapProps {
  coins: MarketCoin[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

/**
 * Semantic colour buckets for 24H change. Greens = up, reds = down, slate =
 * flat/unknown — the same meaning as everywhere else in the app. Colour is
 * never the only signal: every tile with room also prints the signed percent
 * and an arrow, and the legend labels each bucket in words.
 */
const BUCKETS = [
  { min: 7, bg: "#065f46", label: "Up 7% or more" },
  { min: 3, bg: "#047857", label: "Up 3% to 7%" },
  { min: 0.1, bg: "#059669", label: "Up 0.1% to 3%" },
  { min: -0.1, bg: "#475569", label: "Flat (±0.1%)" },
  { min: -3, bg: "#dc2626", label: "Down 0.1% to 3%" },
  { min: -7, bg: "#b91c1c", label: "Down 3% to 7%" },
  { min: -Infinity, bg: "#991b1b", label: "Down 7% or more" },
];

/** `null`/missing change = no data: shown neutral, never as a fake 0%. */
const NO_DATA_BG = "#334155";

export function heatColor(change: number | null | undefined): string {
  if (change === null || change === undefined || !Number.isFinite(change)) return NO_DATA_BG;
  return (BUCKETS.find((bucket) => change >= bucket.min) ?? BUCKETS[BUCKETS.length - 1]).bg;
}

/**
 * Market heatmap: one tile per coin, area scaled with market cap, colour =
 * 24H change. Area uses √(market cap) so mid/small caps stay legible next to
 * BTC; the ordering and relative size still follow market cap. Coins with no
 * market cap are omitted (and counted) rather than given an invented size.
 */
export function MarketHeatmap({ coins, loading, error, onRetry }: MarketHeatmapProps) {
  const navigate = useNavigate();

  const tiles = useMemo(
    () =>
      squarify(
        coins.map((coin) => ({ item: coin, weight: coin.market_cap_usd ? Math.sqrt(coin.market_cap_usd) : null })),
        100,
        100
      ),
    [coins]
  );
  const omitted = coins.length - tiles.length;

  return (
    <section aria-labelledby="market-heatmap-heading" className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <SectionHeading
        id="market-heatmap-heading"
        title="Market Heatmap"
        description="Tile size follows market cap (square-root scale); colour shows 24H change"
      />

      {loading && <div className="h-[360px] animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800 sm:h-[460px]" aria-label="Loading heatmap" />}

      {!loading && error && <RetryError message={error} onRetry={onRetry} />}

      {!loading && !error && tiles.length === 0 && <EmptyState message="No market-cap data is available for the heatmap yet." />}

      {!loading && !error && tiles.length > 0 && (
        <>
          <div className="relative h-[360px] w-full overflow-hidden rounded-lg sm:h-[460px]" role="list" aria-label="Coins by market cap">
            {tiles.map(({ item: coin, x, y, w, h }) => {
              const showSymbol = w >= 4.5 && h >= 7;
              const showChange = w >= 7 && h >= 11;
              const label = `${coin.name} (${coin.symbol.toUpperCase()}), price ${formatUsd(coin.price_usd)}, market cap ${formatCompactUsd(coin.market_cap_usd)}, 24 hour change ${formatPercent(coin.percent_change_24h)}`;
              return (
                <button
                  key={coin.coin_id}
                  type="button"
                  role="listitem"
                  aria-label={label}
                  title={label}
                  onClick={() => navigate(`/coins/${coin.coin_id}`)}
                  className="absolute flex flex-col items-center justify-center overflow-hidden border border-slate-50 p-0.5 text-white transition-[filter] hover:brightness-125 focus:outline-none focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white dark:border-slate-950"
                  style={{ left: `${x}%`, top: `${y}%`, width: `${w}%`, height: `${h}%`, backgroundColor: heatColor(coin.percent_change_24h) }}
                >
                  {showSymbol && <span className={`font-semibold leading-tight ${w >= 12 && h >= 16 ? "text-base" : "text-xs"}`}>{coin.symbol.toUpperCase()}</span>}
                  {showChange && <span className="text-xs tabular-nums leading-tight">{formatPercent(coin.percent_change_24h)}</span>}
                </button>
              );
            })}
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
            <ul className="flex flex-wrap items-center gap-x-3 gap-y-1" aria-label="Colour legend">
              {[...BUCKETS].reverse().map((bucket) => (
                <li key={bucket.label} className="flex items-center gap-1">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: bucket.bg }} aria-hidden="true" />
                  {bucket.label}
                </li>
              ))}
            </ul>
            {omitted > 0 && <p>{omitted} coin{omitted === 1 ? "" : "s"} without market-cap data not shown</p>}
          </div>
        </>
      )}
    </section>
  );
}
