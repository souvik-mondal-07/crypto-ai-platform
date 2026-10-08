import { useMemo, useState } from "react";

import { useAssetHistory } from "../../hooks/useAssetHistory";
import { EmptyState } from "../common/EmptyState";
import { ChangeBadge } from "../common/ChangeBadge";
import { RetryError } from "../common/RetryError";
import { SectionHeading } from "../common/SectionHeading";
import { PerformanceChart } from "./PerformanceChart";
import { periodChangePercent } from "../../utils/chartUtils";
import { formatUsd } from "../../utils/formatters";
import type { MarketCoin, Timeframe } from "../../types/market";

interface MarketPerformanceProps {
  /** Top coins by market cap (the heatmap dataset) — BTC/ETH are resolved from it. */
  coins: MarketCoin[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

type AssetSymbol = "BTC" | "ETH";
const ASSETS: AssetSymbol[] = ["BTC", "ETH"];

/**
 * Ranges the backend can serve (types/market.ts TIMEFRAMES). 1H is listed but
 * disabled: the history endpoint has no sub-daily range and the app does not
 * substitute another one. "24H" is the backend's "1D".
 */
const RANGES: { label: string; value: Timeframe | null }[] = [
  { label: "1H", value: null },
  { label: "24H", value: "1D" },
  { label: "7D", value: "7D" },
  { label: "30D", value: "30D" },
  { label: "90D", value: "90D" },
  { label: "1Y", value: "1Y" },
];

const pill = (selected: boolean, disabled = false) =>
  `rounded-md px-2.5 py-1 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
    disabled
      ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
      : selected
        ? "bg-slate-900 text-white dark:bg-sky-600"
        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
  }`;

/**
 * Market performance: price history for BTC or ETH over the supported ranges.
 *
 * Total-market history is NOT offered — the backend has no historical
 * total-market-cap series, and it would be dishonest to chart anything else
 * under that name. The disabled control says so instead of hiding the gap.
 */
export function MarketPerformance({ coins, loading, error, onRetry }: MarketPerformanceProps) {
  const [asset, setAsset] = useState<AssetSymbol>("BTC");
  const [timeframe, setTimeframe] = useState<Timeframe>("7D");

  const coinsBySymbol = useMemo(() => {
    const map: Partial<Record<AssetSymbol, MarketCoin>> = {};
    // `coins` is sorted by market cap, so the first symbol match is the real
    // one even if a lookalike token reuses the symbol.
    for (const symbol of ASSETS) map[symbol] = coins.find((coin) => coin.symbol.toUpperCase() === symbol);
    return map;
  }, [coins]);

  const selected = coinsBySymbol[asset];
  const history = useAssetHistory(selected?.coin_id, timeframe);
  const change = periodChangePercent(history.candles);
  const rangeLabel = RANGES.find((range) => range.value === timeframe)?.label ?? timeframe;

  const noAssets = !loading && !error && ASSETS.every((symbol) => !coinsBySymbol[symbol]);

  return (
    <section aria-labelledby="market-performance-heading" className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <SectionHeading
        id="market-performance-heading"
        title="Market Performance"
        description="Price history from the synced market data"
        actions={
          <div role="group" aria-label="Time range" className="flex flex-wrap gap-0.5 rounded-lg border border-slate-200 p-0.5 dark:border-slate-700">
            {RANGES.map((range) => (
              <button
                key={range.label}
                type="button"
                disabled={range.value === null}
                aria-pressed={range.value === timeframe}
                title={range.value === null ? "1-hour history isn't available from the data provider" : undefined}
                onClick={() => range.value && setTimeframe(range.value)}
                className={pill(range.value === timeframe, range.value === null)}
              >
                {range.label}
              </button>
            ))}
          </div>
        }
      />

      <div role="group" aria-label="Asset" className="mb-3 flex flex-wrap items-center gap-1">
        {ASSETS.map((symbol) => (
          <button
            key={symbol}
            type="button"
            disabled={!coinsBySymbol[symbol]}
            aria-pressed={asset === symbol}
            onClick={() => setAsset(symbol)}
            className={pill(asset === symbol, !coinsBySymbol[symbol])}
          >
            {symbol}
          </button>
        ))}
        <button
          type="button"
          disabled
          title="Total market history isn't available yet — the backend doesn't provide a historical total-market series."
          className={pill(false, true)}
        >
          Total Market
        </button>
      </div>

      {loading && (
        <div className="h-[320px] animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" aria-label="Loading chart" />
      )}

      {!loading && error && <RetryError message={error} onRetry={onRetry} />}

      {noAssets && <EmptyState message="BTC and ETH aren't in the synced market data yet." />}

      {!loading && !error && selected && (
        <>
          <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <p className="text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-50">{formatUsd(selected.price_usd)}</p>
            {!history.loading && !history.error && change !== null && (
              <p className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
                <ChangeBadge value={change} variant="pill" /> over {rangeLabel}
              </p>
            )}
          </div>

          {history.loading && (
            <div className="h-[320px] animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" aria-label="Loading price history" />
          )}
          {!history.loading && history.error && <RetryError message={history.error} onRetry={history.retry} />}
          {!history.loading && !history.error && history.candles.length === 0 && (
            <EmptyState message="No price history is available for this range." />
          )}
          {!history.loading && !history.error && history.candles.length > 0 && (
            <PerformanceChart
              candles={history.candles}
              positive={(change ?? 0) >= 0}
              ariaLabel={`${asset} price over ${rangeLabel}`}
            />
          )}
        </>
      )}
    </section>
  );
}
