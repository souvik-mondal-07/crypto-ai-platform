import { useNavigate } from "react-router-dom";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Info, Star } from "lucide-react";
import type { ReactNode } from "react";

import { ChangeBadge } from "../common/ChangeBadge";
import { EmptyState } from "../common/EmptyState";
import { FreshnessBadge } from "../common/FreshnessBadge";
import { RetryError } from "../common/RetryError";
import { CoinLogo } from "../market/CoinLogo";
import { COLUMNS, type ColumnKey } from "../../utils/marketColumns";
import { formatCompactUsd, formatPlainPercent, formatSupply, formatUsd } from "../../utils/formatters";
import type { MarketCoin, MarketCoinSortField } from "../../types/market";

interface MarketsTableProps {
  coins: MarketCoin[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  sortBy: MarketCoinSortField;
  sortDirection: "asc" | "desc";
  onSort: (field: MarketCoinSortField) => void;
  page: number;
  pages: number;
  total: number;
  limit: number;
  onPageChange: (page: number) => void;
  visible: ColumnKey[];
  watchlist: string[];
  onToggleWatch: (coinId: string) => void;
  compare: string[];
  onToggleCompare: (coinId: string) => void;
  emptyMessage: string;
  emptyAction?: ReactNode;
}

const num = "px-3 py-3 text-right tabular-nums text-slate-600 dark:text-slate-300";

function cell(key: ColumnKey, coin: MarketCoin): ReactNode {
  switch (key) {
    case "price":
      return <td key={key} className={`${num} font-medium text-slate-800 dark:text-slate-100`}>{formatUsd(coin.price_usd)}</td>;
    case "change_24h":
      return <td key={key} className="px-3 py-3 text-right"><ChangeBadge value={coin.percent_change_24h} /></td>;
    case "change_7d":
      return <td key={key} className="px-3 py-3 text-right"><ChangeBadge value={coin.percent_change_7d} /></td>;
    case "market_cap":
      return <td key={key} className={num}>{formatCompactUsd(coin.market_cap_usd)}</td>;
    case "volume":
      return <td key={key} className={num}>{formatCompactUsd(coin.volume_24h_usd)}</td>;
    case "fdv":
      return <td key={key} className={num}>{formatCompactUsd(coin.fully_diluted_valuation_usd)}</td>;
    case "supply":
      return <td key={key} className={num}>{formatSupply(coin.circulating_supply)}</td>;
    case "volatility":
      return <td key={key} className={num}>{formatPlainPercent(coin.volatility_24h_pct ?? null, 1)}</td>;
    case "ath":
      return <td key={key} className={num}>{formatUsd(coin.ath_usd)}</td>;
    case "atl":
      return <td key={key} className={num}>{formatUsd(coin.atl_usd)}</td>;
    case "status":
      return <td key={key} className="px-3 py-3 text-center"><FreshnessBadge lastUpdated={coin.last_updated} isStale={coin.is_stale} dotOnly /></td>;
  }
}

/**
 * The Markets explorer table. Sorting and pagination are server-side (the
 * browser only ever holds the current page). Row click opens Coin Details;
 * the star and compare checkbox stop propagation so they never navigate.
 * The table scrolls horizontally inside its own container, and the Coin
 * column is sticky so it stays visible while scrolling on small screens.
 */
export function MarketsTable({
  coins, loading, error, onRetry, sortBy, sortDirection, onSort, page, pages, total, limit, onPageChange,
  visible, watchlist, onToggleWatch, compare, onToggleCompare, emptyMessage, emptyAction,
}: MarketsTableProps) {
  const navigate = useNavigate();
  const shown = COLUMNS.filter((column) => visible.includes(column.key));

  if (error) {
    return <div className="p-4"><RetryError message={error} onRetry={onRetry} /></div>;
  }
  if (!loading && coins.length === 0) {
    return <EmptyState message={emptyMessage} action={emptyAction} />;
  }

  const from = total === 0 ? 0 : (page - 1) * limit + 1;
  const to = Math.min(page * limit, total);

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-slate-100 text-xs uppercase text-slate-400 dark:border-slate-800">
            <tr>
              <th scope="col" className="w-10 px-3 py-2"><span className="sr-only">Compare</span></th>
              <th scope="col" className="w-8 px-1 py-2"><span className="sr-only">Watchlist</span></th>
              <th scope="col" className="px-3 py-2 font-medium">#</th>
              <th scope="col" className="sticky left-0 z-[1] bg-white px-3 py-2 font-medium dark:bg-slate-900">Coin</th>
              {shown.map((column) => {
                const isSorted = column.sortField !== undefined && column.sortField === sortBy;
                const alignment = column.key === "status" ? "text-center" : "text-right";
                const label = (
                  <>
                    {column.label}
                    {column.help && (
                      <span title={column.help} className="ml-1 inline-flex align-middle text-slate-300 dark:text-slate-600">
                        <Info className="h-3 w-3" aria-hidden="true" />
                        <span className="sr-only">{column.help}</span>
                      </span>
                    )}
                  </>
                );
                if (!column.sortField) {
                  return <th key={column.key} scope="col" className={`whitespace-nowrap px-3 py-2 font-medium ${alignment}`}>{label}</th>;
                }
                return (
                  <th
                    key={column.key}
                    scope="col"
                    className={`whitespace-nowrap px-3 py-2 font-medium ${alignment}`}
                    aria-sort={isSorted ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
                  >
                    <button
                      type="button"
                      onClick={() => onSort(column.sortField as MarketCoinSortField)}
                      className={`inline-flex items-center gap-1 uppercase hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:hover:text-slate-200 ${isSorted ? "text-slate-700 dark:text-slate-200" : ""}`}
                    >
                      {label}
                      {isSorted && (sortDirection === "asc" ? <ArrowUp className="h-3 w-3" aria-hidden="true" /> : <ArrowDown className="h-3 w-3" aria-hidden="true" />)}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 10 }).map((_, i) => (
                <tr key={i} className="animate-pulse border-b border-slate-50 dark:border-slate-800" aria-hidden="true">
                  {Array.from({ length: 4 + shown.length }).map((__, j) => (
                    <td key={j} className="px-3 py-3"><div className={`h-3 rounded bg-slate-200 dark:bg-slate-800 ${j === 3 ? "w-24" : "w-12"}`} /></td>
                  ))}
                </tr>
              ))}

            {!loading && coins.map((coin) => {
              const starred = watchlist.includes(coin.coin_id);
              const selected = compare.includes(coin.coin_id);
              return (
                <tr
                  key={coin.coin_id}
                  onClick={() => navigate(`/coins/${coin.coin_id}`)}
                  className="group cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60"
                >
                  <td className="px-3 py-3" onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => onToggleCompare(coin.coin_id)}
                      aria-label={`Compare ${coin.name}`}
                      className="h-4 w-4 rounded border-slate-300"
                    />
                  </td>
                  <td className="px-1 py-3" onClick={(event) => event.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => onToggleWatch(coin.coin_id)}
                      aria-pressed={starred}
                      aria-label={starred ? `Remove ${coin.name} from watchlist` : `Add ${coin.name} to watchlist`}
                      title={starred ? "Remove from watchlist" : "Add to watchlist"}
                      className="rounded p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                    >
                      <Star className={`h-4 w-4 ${starred ? "fill-amber-400 text-amber-400" : "text-slate-300 hover:text-amber-400 dark:text-slate-600"}`} aria-hidden="true" />
                    </button>
                  </td>
                  <td className="px-3 py-3 tabular-nums text-slate-500">{coin.market_cap_rank ?? "—"}</td>
                  <td className="sticky left-0 z-[1] bg-white px-3 py-3 group-hover:bg-slate-50 dark:bg-slate-900 dark:group-hover:bg-slate-800">
                    <div className="flex items-center gap-2">
                      <CoinLogo src={coin.logo_url} alt="" />
                      <div className="min-w-0">
                        <p className="max-w-[160px] truncate font-medium text-slate-800 dark:text-slate-100">{coin.name}</p>
                        <p className="text-xs text-slate-400">{coin.symbol.toUpperCase()}</p>
                      </div>
                    </div>
                  </td>
                  {shown.map((column) => cell(column.key, coin))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!loading && pages > 0 && (
        <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-3 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
          <span className="text-xs">Showing {from.toLocaleString()}–{to.toLocaleString()} of {total.toLocaleString()}</span>
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => onPageChange(Math.max(1, page - 1))} disabled={page <= 1} className="flex items-center gap-1 rounded p-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-30">
              <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Prev
            </button>
            <span>Page {page} of {pages}</span>
            <button type="button" onClick={() => onPageChange(Math.min(pages, page + 1))} disabled={page >= pages} className="flex items-center gap-1 rounded p-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-30">
              Next <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </nav>
      )}
    </div>
  );
}
