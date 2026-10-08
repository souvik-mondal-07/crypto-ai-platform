import {
  changeColorClass,
  formatAbsoluteDateTime,
  formatCompactUsd,
  formatPercent,
  formatSupply,
  formatUsd,
} from "../../utils/formatters";
import type { Coin } from "../../types/coin";
import type { MarketData } from "../../types/market";

interface CoinStatsProps {
  coin: Coin;
  market: MarketData | null;
}

function StatCard({ label, value, valueClassName }: { label: string; value: string; valueClassName?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1.5 text-base font-semibold text-slate-900 dark:text-slate-100 ${valueClassName ?? ""}`}>
        {value}
      </p>
    </div>
  );
}

/** Market statistics. Every unavailable field renders "N/A" via the formatters — never a fabricated number. */
export function CoinMarketStats({ coin, market }: CoinStatsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9">
      <StatCard label="Market Cap" value={formatCompactUsd(market?.market_cap_usd)} />
      <StatCard label="24h Volume" value={formatCompactUsd(market?.volume_24h_usd)} />
      <StatCard label="24h High" value={formatUsd(market?.high_24h_usd)} />
      <StatCard label="24h Low" value={formatUsd(market?.low_24h_usd)} />
      <StatCard label="Rank" value={coin.market_cap_rank ? `#${coin.market_cap_rank}` : "N/A"} />
      <StatCard label="Circulating Supply" value={formatSupply(market?.circulating_supply)} />
      <StatCard label="Total Supply" value={formatSupply(market?.total_supply)} />
      <StatCard label="Max Supply" value={formatSupply(market?.max_supply)} />
      <StatCard label="Fully Diluted Valuation" value={formatCompactUsd(market?.fully_diluted_valuation_usd)} />
    </div>
  );
}

/**
 * Price performance across the periods the backend supplies. A period
 * the backend returned as null renders "N/A" rather than being hidden
 * or guessed at.
 */
export function CoinPricePerformance({ market }: { market: MarketData | null }) {
  const periods: { label: string; value: number | null | undefined }[] = [
    { label: "1h", value: market?.percent_change_1h },
    { label: "24h", value: market?.percent_change_24h },
    { label: "7d", value: market?.percent_change_7d },
    { label: "30d", value: market?.percent_change_30d },
    { label: "1y", value: market?.percent_change_1y },
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">Price Performance</h3>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {periods.map(({ label, value }) => (
          <div key={label}>
            <dt className="text-xs uppercase text-slate-400">{label}</dt>
            <dd className={`mt-0.5 text-sm font-semibold ${changeColorClass(value)}`}>{formatPercent(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * All-time high/low. The backend supplies the change percentages
 * directly (`ath_change_percentage`/`atl_change_percentage`), so those
 * are used as-is rather than recomputed from price — recomputing would
 * disagree with the provider whenever the price snapshot and the
 * ATH/ATL snapshot were taken at different moments. Dates are the
 * provider's own record of when each was reached, shown only when
 * the backend actually returned one.
 */
export function CoinAthAtl({ market }: { market: MarketData | null }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">All-Time High / Low</h3>
      <dl className="grid grid-cols-2 gap-4">
        <div>
          <dt className="text-xs uppercase text-slate-400">All-Time High</dt>
          <dd className="mt-0.5 text-sm font-semibold text-slate-900 dark:text-slate-100">
            {formatUsd(market?.ath_usd)}
          </dd>
          <dd className={`text-xs font-medium ${changeColorClass(market?.ath_change_percentage)}`}>
            {formatPercent(market?.ath_change_percentage)} from ATH
          </dd>
          {market?.ath_date && (
            <dd className="text-xs text-slate-400">{formatAbsoluteDateTime(market.ath_date)}</dd>
          )}
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-400">All-Time Low</dt>
          <dd className="mt-0.5 text-sm font-semibold text-slate-900 dark:text-slate-100">
            {formatUsd(market?.atl_usd)}
          </dd>
          <dd className={`text-xs font-medium ${changeColorClass(market?.atl_change_percentage)}`}>
            {formatPercent(market?.atl_change_percentage)} from ATL
          </dd>
          {market?.atl_date && (
            <dd className="text-xs text-slate-400">{formatAbsoluteDateTime(market.atl_date)}</dd>
          )}
        </div>
      </dl>
    </div>
  );
}
