import { useMemo, useState } from "react";

import { useAssetHistory } from "../../hooks/useAssetHistory";
import { EmptyState } from "../common/EmptyState";
import { ChangeBadge } from "../common/ChangeBadge";
import { RetryError } from "../common/RetryError";
import { CoinLogo } from "../market/CoinLogo";
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
 * Ranges the backend can serve (types/market.ts TIMEFRAMES): 1D, 7D, 1M (=30D), 3M (=90D) and 1Y. "ALL" is listed
 * but disabled: the history endpoint has no all-time range and the app does not substitute another one.
 */
const RANGES: { label: string; value: Timeframe | null }[] = [
  { label: "1D", value: "1D" },
  { label: "7D", value: "7D" },
  { label: "1M", value: "30D" },
  { label: "3M", value: "90D" },
  { label: "1Y", value: "1Y" },
  { label: "ALL", value: null },
];

const pill = (selected: boolean, disabled = false) =>
  `segmented-item ${selected && !disabled ? "segmented-item-active" : ""}`;

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
    <section aria-labelledby="market-performance-heading" className="card card-pad">
      <h2 id="market-performance-heading" className="sr-only">Market Performance</h2>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <CoinLogo src={selected?.logo_url ?? null} alt="" size={28} />
          <p className="min-w-0 truncate text-sm font-semibold text-slate-900 dark:text-white">
            {selected ? `${selected.name} (${selected.symbol.toUpperCase()})` : asset}
          </p>
        </div>
        <div role="group" aria-label="Time range" className="segmented flex-wrap">
          {RANGES.map((range) => (
            <button
              key={range.label}
              type="button"
              disabled={range.value === null}
              aria-pressed={range.value === timeframe}
              title={range.value === null ? "All-time history isn't available from the data provider" : undefined}
              onClick={() => range.value && setTimeframe(range.value)}
              className={pill(range.value === timeframe, range.value === null)}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      <div role="group" aria-label="Asset" className="segmented mb-3 flex-wrap">
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
        <div className="h-[260px] animate-pulse rounded-lg bg-slate-100 motion-reduce:animate-none dark:bg-slate-800 sm:h-[300px]" aria-label="Loading chart" />
      )}

      {!loading && error && <RetryError message={error} onRetry={onRetry} />}

      {noAssets && <EmptyState message="BTC and ETH aren't in the synced market data yet." />}

      {!loading && !error && selected && (
        <>
          <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <p className="text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">{formatUsd(selected.price_usd)}</p>
            {!history.loading && !history.error && change !== null && (
              <p className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
                <ChangeBadge value={change} variant="pill" /> over {rangeLabel}
              </p>
            )}
          </div>

          {history.loading && (
            <div className="h-[260px] animate-pulse rounded-lg bg-slate-100 motion-reduce:animate-none dark:bg-slate-800 sm:h-[300px]" aria-label="Loading price history" />
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
