import { useNavigate } from "react-router-dom";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";

import { CoinLogo } from "./CoinLogo";
import { SkeletonRow } from "./Skeletons";
import { EmptyState } from "../common/EmptyState";
import { ErrorMessage } from "../common/ErrorMessage";
import { changeColorClass, formatCompactUsd, formatPercent, formatUsd } from "../../utils/formatters";
import type { MarketSortField, SortDirection } from "../../store/marketStore";
import type { Coin, CoinSearchResult } from "../../types/coin";
import type { MarketData } from "../../types/market";

/** A row is either a plain Coin (market data looked up via `coinMarketData`)
 * or a CoinSearchResult, which already carries its market data joined in —
 * no lookup needed for search rows. */
type CoinTableRow = Coin | CoinSearchResult;

function isSearchResult(coin: CoinTableRow): coin is CoinSearchResult {
  return "price_usd" in coin;
}

/** Resolves a row's market fields — from the row itself if it's a joined
 * CoinSearchResult, otherwise from the per-coin `coinMarketData` map. */
function resolveMarket(coin: CoinTableRow, coinMarketData: Record<string, MarketData>): MarketData | null {
  if (isSearchResult(coin)) {
    return {
      coin_id: coin.id,
      price_usd: coin.price_usd,
      market_cap_usd: coin.market_cap_usd,
      volume_24h_usd: coin.volume_24h_usd,
      high_24h_usd: coin.high_24h_usd,
      low_24h_usd: coin.low_24h_usd,
      percent_change_1h: null,
      percent_change_24h: coin.percent_change_24h,
      percent_change_7d: coin.percent_change_7d,
      percent_change_30d: null,
      percent_change_1y: null,
      price_change_24h_usd: null,
      circulating_supply: null,
      total_supply: null,
      max_supply: null,
      fully_diluted_valuation_usd: null,
      ath_usd: null,
      atl_usd: null,
      ath_change_percentage: null,
      atl_change_percentage: null,
      ath_date: null,
      atl_date: null,
      last_updated: null,
      data_source: "joined",
      is_stale: false,
    };
  }
  return coinMarketData[coin.id] ?? null;
}

interface CoinTableProps {
  coins: CoinTableRow[];
  coinMarketData: Record<string, MarketData>;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  sortBy?: MarketSortField;
  sortDirection?: SortDirection;
  onSort?: (field: MarketSortField) => void;
  page?: number;
  pages?: number;
  onPageChange?: (page: number) => void;
  emptyMessage?: string;
}

const SORTABLE_COLUMNS: { field: MarketSortField; label: string }[] = [
  { field: "market_cap_rank", label: "Rank" },
  { field: "name", label: "Coin" },
];

export function CoinTable({
  coins,
  coinMarketData,
  loading,
  error,
  onRetry,
  sortBy,
  sortDirection,
  onSort,
  page,
  pages,
  onPageChange,
  emptyMessage = "No cryptocurrencies found.",
}: CoinTableProps) {
  const navigate = useNavigate();

  function renderSortIcon(field: MarketSortField) {
    if (!onSort || sortBy !== field) return null;
    return sortDirection === "asc" ? (
      <ArrowUp className="ml-1 inline h-3 w-3" aria-hidden="true" />
    ) : (
      <ArrowDown className="ml-1 inline h-3 w-3" aria-hidden="true" />
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <ErrorMessage message={error} />
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 text-sm font-medium text-sky-600 hover:underline dark:text-sky-400"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!loading && coins.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-slate-100 text-xs uppercase text-slate-400 dark:border-slate-800">
            <tr>
              {SORTABLE_COLUMNS.map(({ field, label }) => (
                <th
                  key={field}
                  className={`px-4 py-2 font-medium ${onSort ? "cursor-pointer select-none" : ""}`}
                  onClick={() => onSort?.(field)}
                >
                  {label}
                  {renderSortIcon(field)}
                </th>
              ))}
              <th className="px-4 py-2 font-medium">Symbol</th>
              <th className="px-4 py-2 font-medium">Price</th>
              <th className="px-4 py-2 font-medium">24h</th>
              <th className="px-4 py-2 font-medium">7d</th>
              <th className="px-4 py-2 font-medium">Market Cap</th>
              <th className="px-4 py-2 font-medium">Volume (24h)</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)}

            {!loading &&
              coins.map((coin) => {
                const market = resolveMarket(coin, coinMarketData);
                return (
                  <tr
                    key={coin.id}
                    onClick={() => navigate(`/coins/${coin.id}`)}
                    className="cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60"
                  >
                    <td className="px-4 py-3 text-slate-500">{coin.market_cap_rank ?? "—"}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <CoinLogo src={coin.logo_url} alt={coin.name} />
                        <span className="max-w-[140px] truncate font-medium text-slate-800 dark:text-slate-100">
                          {coin.name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{coin.symbol}</td>
                    <td className="px-4 py-3 font-medium text-slate-800 dark:text-slate-100">
                      {market ? formatUsd(market.price_usd) : "—"}
                    </td>
                    <td className={`px-4 py-3 font-medium ${market ? changeColorClass(market.percent_change_24h) : "text-slate-400"}`}>
                      {market ? formatPercent(market.percent_change_24h) : "—"}
                    </td>
                    <td className={`px-4 py-3 font-medium ${market ? changeColorClass(market.percent_change_7d) : "text-slate-400"}`}>
                      {market ? formatPercent(market.percent_change_7d) : "—"}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {market ? formatCompactUsd(market.market_cap_usd) : "—"}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {market ? formatCompactUsd(market.volume_24h_usd) : "—"}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {!loading && onPageChange && pages !== undefined && pages > 1 && page !== undefined && (
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500 dark:border-slate-800">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="flex items-center gap-1 rounded p-1 disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" /> Prev
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button
            type="button"
            onClick={() => onPageChange(Math.min(pages, page + 1))}
            disabled={page >= pages}
            className="flex items-center gap-1 rounded p-1 disabled:opacity-30"
          >
            Next <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
