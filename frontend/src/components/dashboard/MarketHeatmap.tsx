import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { EmptyState } from "../common/EmptyState";
import { RetryError } from "../common/RetryError";
import { SectionHeading } from "../common/SectionHeading";
import { CoinLogo } from "../market/CoinLogo";
import { formatCompactUsd, formatPercent, formatUsd } from "../../utils/formatters";
import { squarify } from "../../utils/treemap";
import type { MarketCoin } from "../../types/market";

interface MarketHeatmapProps {
  coins: MarketCoin[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  /**
   * Dashboard variant: only the 9 largest coins get their own tile and the rest are summed into one "Others" tile
   * (sized by their combined market cap, coloured by their market-cap-weighted 24H change, linking to Markets).
   */
  compact?: boolean;
}

const COMPACT_TILES = 9;

interface HeatTile {
  key: string;
  coin: MarketCoin | null;
  symbol: string;
  change: number | null;
  /** How many coins an aggregate tile stands for. */
  count?: number;
}

/** Market-cap-weighted mean of the known 24H changes; null when none of the coins has one (never a made-up 0). */
function weightedChange(coins: MarketCoin[]): number | null {
  let weight = 0;
  let sum = 0;
  for (const coin of coins) {
    if (typeof coin.percent_change_24h === "number" && Number.isFinite(coin.percent_change_24h) && coin.market_cap_usd) {
      weight += coin.market_cap_usd;
      sum += coin.percent_change_24h * coin.market_cap_usd;
    }
  }
  return weight > 0 ? sum / weight : null;
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
export function MarketHeatmap({ coins, loading, error, onRetry, compact = false }: MarketHeatmapProps) {
  const navigate = useNavigate();

  const { tiles, eligibleCount } = useMemo(() => {
    const toTile = (coin: MarketCoin): HeatTile => ({ key: coin.coin_id, coin, symbol: coin.symbol.toUpperCase(), change: coin.percent_change_24h });
    const eligible = coins.filter((coin) => typeof coin.market_cap_usd === "number" && coin.market_cap_usd > 0);
    if (!compact) {
      return {
        tiles: squarify(
          coins.map((coin) => ({ item: toTile(coin), weight: coin.market_cap_usd ? Math.sqrt(coin.market_cap_usd) : null })),
          100,
          100
        ),
        eligibleCount: eligible.length,
      };
    }
    const ranked = [...eligible].sort((a, b) => (b.market_cap_usd ?? 0) - (a.market_cap_usd ?? 0));
    const top = ranked.slice(0, COMPACT_TILES);
    const rest = ranked.slice(COMPACT_TILES);
    const items = top.map((coin) => ({ item: toTile(coin), weight: Math.sqrt(coin.market_cap_usd ?? 0) as number | null }));
    if (rest.length > 0) {
      const restCap = rest.reduce((sum, coin) => sum + (coin.market_cap_usd ?? 0), 0);
      items.push({ item: { key: "__others__", coin: null, symbol: "Others", change: weightedChange(rest), count: rest.length }, weight: Math.sqrt(restCap) });
    }
    return { tiles: squarify(items, 100, 100), eligibleCount: eligible.length };
  }, [coins, compact]);
  const omitted = coins.length - eligibleCount;
  const height = compact ? "h-[300px] sm:h-[340px]" : "h-[360px] sm:h-[460px]";

  return (
    <section aria-labelledby="market-heatmap-heading" className="card card-pad">
      <SectionHeading
        id="market-heatmap-heading"
        title={compact ? "Crypto Heatmap" : "Market Heatmap"}
        description={compact ? undefined : "Tile size follows market cap (square-root scale); colour shows 24H change"}
        actions={
          compact ? (
            <Link to="/markets" className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:underline dark:text-sky-400">
              View All <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          ) : undefined
        }
      />

      {loading && <div className={`${height} animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800`} aria-label="Loading heatmap" />}

      {!loading && error && <RetryError message={error} onRetry={onRetry} />}

      {!loading && !error && tiles.length === 0 && <EmptyState message="No market-cap data is available for the heatmap yet." />}

      {!loading && !error && tiles.length > 0 && (
        <>
          <div className={`relative ${height} w-full overflow-hidden rounded-lg`} role="list" aria-label="Coins by market cap">
            {tiles.map(({ item: tile, x, y, w, h }) => {
              const showSymbol = w >= 4.5 && h >= 7;
              const showChange = w >= 7 && h >= 11;
              const showLogo = !!tile.coin && w >= 14 && h >= 22;
              const label = tile.coin
                ? `${tile.coin.name} (${tile.symbol}), price ${formatUsd(tile.coin.price_usd)}, market cap ${formatCompactUsd(tile.coin.market_cap_usd)}, 24 hour change ${formatPercent(tile.change)}`
                : `Other coins (${tile.count}), market-cap-weighted 24 hour change ${formatPercent(tile.change)}`;
              return (
                <button
                  key={tile.key}
                  type="button"
                  role="listitem"
                  aria-label={label}
                  title={label}
                  onClick={() => navigate(tile.coin ? `/coins/${tile.coin.coin_id}` : "/markets")}
                  className={`absolute flex flex-col items-center justify-center overflow-hidden border border-slate-50 p-0.5 text-white transition-[filter] hover:brightness-125 focus:outline-none focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white dark:border-slate-950 ${compact ? "rounded-lg border-2" : ""}`}
                  style={{
                    left: `${x}%`,
                    top: `${y}%`,
                    width: `${w}%`,
                    height: `${h}%`,
                    backgroundColor: heatColor(tile.change),
                    ...(compact ? { backgroundImage: "linear-gradient(145deg, rgba(255,255,255,0.22), rgba(0,0,0,0.12))" } : {}),
                  }}
                >
                  {showLogo && tile.coin && <CoinLogo src={tile.coin.logo_url} alt="" size={compact ? 24 : 20} />}
                  {showSymbol && <span className={`font-semibold leading-tight ${w >= 12 && h >= 16 ? "text-base" : "text-xs"}`}>{tile.symbol}</span>}
                  {showChange && <span className="text-xs tabular-nums leading-tight">{formatPercent(tile.change)}</span>}
                </button>
              );
            })}
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
            <ul className={`flex flex-wrap items-center gap-x-3 gap-y-1 ${compact ? "hidden" : ""}`} aria-label="Colour legend">
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
