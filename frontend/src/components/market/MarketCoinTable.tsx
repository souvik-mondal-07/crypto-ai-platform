import { useNavigate } from "react-router-dom";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";

import { CoinLogo } from "./CoinLogo";
import { SkeletonRow } from "./Skeletons";
import { EmptyState } from "../common/EmptyState";
import { ErrorMessage } from "../common/ErrorMessage";
import {
  changeColorClass,
  formatCompactUsd,
  formatPercent,
  formatSupply,
  formatUsd,
} from "../../utils/formatters";
import type { MarketCoin, MarketCoinSortField } from "../../types/market";

interface MarketCoinTableProps {
  coins: MarketCoin[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  sortBy: MarketCoinSortField;
  sortDirection: "asc" | "desc";
  onSort: (field: MarketCoinSortField) => void;
  page: number;
  pages: number;
  onPageChange: (page: number) => void;
  emptyMessage?: string;
}

/** Columns backed by a server-sortable field carry a `sortField`; the rest are display-only. */
const COLUMNS: { label: string; sortField?: MarketCoinSortField; numeric?: boolean }[] = [
  { label: "#" },
  { label: "Coin" },
  { label: "Price", sortField: "price", numeric: true },
  { label: "24h %", sortField: "change_24h", numeric: true },
  { label: "24h High", numeric: true },
  { label: "24h Low", numeric: true },
  { label: "Market Cap", sortField: "market_cap", numeric: true },
  { label: "Volume (24h)", sortField: "volume", numeric: true },
  { label: "Circulating Supply", numeric: true },
];

export function MarketCoinTable({
  coins,
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
}: MarketCoinTableProps) {
  const navigate = useNavigate();

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
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="border-b border-slate-100 text-xs uppercase text-slate-400 dark:border-slate-800">
            <tr>
              {COLUMNS.map((column) => {
                const isSorted = column.sortField !== undefined && column.sortField === sortBy;
                const alignment = column.numeric ? "text-right" : "text-left";

                if (!column.sortField) {
                  return (
                    <th key={column.label} className={`px-4 py-2 font-medium ${alignment}`}>
                      {column.label}
                    </th>
                  );
                }

                return (
                  <th
                    key={column.label}
                    className={`px-4 py-2 font-medium ${alignment}`}
                    aria-sort={isSorted ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
                  >
                    <button
                      type="button"
                      onClick={() => onSort(column.sortField as MarketCoinSortField)}
                      className={`inline-flex items-center gap-1 uppercase hover:text-slate-600 dark:hover:text-slate-200 ${
                        isSorted ? "text-slate-700 dark:text-slate-200" : ""
                      }`}
                    >
                      {column.label}
                      {isSorted &&
                        (sortDirection === "asc" ? (
                          <ArrowUp className="h-3 w-3" aria-hidden="true" />
                        ) : (
                          <ArrowDown className="h-3 w-3" aria-hidden="true" />
                        ))}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 10 }).map((_, i) => <SkeletonRow key={i} />)}

            {!loading &&
              coins.map((coin) => (
                <tr
                  key={coin.coin_id}
                  onClick={() => navigate(`/coins/${coin.coin_id}`)}
                  className="cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60"
                >
                  <td className="px-4 py-3 text-slate-500">{coin.market_cap_rank ?? "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <CoinLogo src={coin.logo_url} alt={coin.name} />
                      <div className="min-w-0">
                        <p className="max-w-[160px] truncate font-medium text-slate-800 dark:text-slate-100">
                          {coin.name}
                        </p>
                        <p className="text-xs text-slate-400">{coin.symbol}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-slate-800 dark:text-slate-100">
                    {formatUsd(coin.price_usd)}
                  </td>
                  <td className={`px-4 py-3 text-right font-medium ${changeColorClass(coin.percent_change_24h)}`}>
                    {formatPercent(coin.percent_change_24h)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-300">
                    {formatUsd(coin.high_24h_usd)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-300">
                    {formatUsd(coin.low_24h_usd)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-300">
                    {formatCompactUsd(coin.market_cap_usd)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-300">
                    {formatCompactUsd(coin.volume_24h_usd)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-300">
                    {formatSupply(coin.circulating_supply)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {!loading && pages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="flex items-center gap-1 rounded p-1 disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Prev
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
            Next <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  );
}
