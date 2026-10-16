import { EmptyState } from "../common/EmptyState";
import { Pagination } from "../common/Pagination";
import { RetryError } from "../common/RetryError";
import type { BacktestTrade, Paged } from "../../types/backtesting";
import { formatAbsoluteDateTime, formatNumber, formatUsd } from "../../utils/backtestFormat";

interface TradesTableProps {
  trades: Paged<BacktestTrade> | null;
  error: string | null;
  truncated: boolean;
  onPage: (page: number) => void;
  onRetry: () => void;
}

/** Simulated fills, in execution order, paginated. */
export function TradesTable({ trades, error, truncated, onPage, onRetry }: TradesTableProps) {
  if (error) return <RetryError message={error} onRetry={onRetry} />;
  if (trades === null) return <p role="status" className="text-sm text-slate-500 dark:text-slate-400">Loading trades...</p>;
  if (trades.items.length === 0) return <EmptyState message="This backtest made no trades." />;
  const pages = Math.max(1, Math.ceil(trades.total / trades.limit));

  return (
    <div>
      <div className="table-wrap">
        <table className="w-full text-sm" aria-label="Trade history">
          <thead className="table-head">
            <tr>
              <th scope="col" className="px-3 py-2 text-left">Executed</th>
              <th scope="col" className="px-3 py-2 text-left">Coin</th>
              <th scope="col" className="px-3 py-2 text-left">Side</th>
              <th scope="col" className="px-3 py-2 text-right">Price</th>
              <th scope="col" className="px-3 py-2 text-right">Quantity</th>
              <th scope="col" className="px-3 py-2 text-right">Notional</th>
              <th scope="col" className="px-3 py-2 text-right">Fee</th>
              <th scope="col" className="px-3 py-2 text-right">Slippage</th>
              <th scope="col" className="px-3 py-2 text-left">Reason</th>
            </tr>
          </thead>
          <tbody>
            {trades.items.map((trade, index) => (
              <tr key={`${trade.execution_time}-${trade.coin_id}-${trade.side}-${index}`} className="table-row">
                <td className="whitespace-nowrap px-3 py-2">{formatAbsoluteDateTime(trade.execution_time)}</td>
                <td className="px-3 py-2">{trade.symbol ?? trade.coin_id}</td>
                <td className="px-3 py-2 font-medium">{trade.side}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatUsd(trade.price)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatNumber(trade.quantity, 6)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatUsd(trade.notional)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatUsd(trade.fee)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatUsd(trade.slippage_cost)}</td>
                <td className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">{trade.reason === "end_of_backtest" ? "Closed at end of period" : "Phase 14 decision"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={trades.page} pages={pages} onPageChange={onPage} label="trades" />
      {truncated && <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Only the first {trades.total} trades are stored for this run.</p>}
    </div>
  );
}
