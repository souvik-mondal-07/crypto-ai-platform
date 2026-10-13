import { Link } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";

import type { Holding } from "../../types/userFeatures";
import { changeColorClass, formatPercent, formatUsd } from "../../utils/formatters";
import { ChangeBadge } from "../common/ChangeBadge";
import { CoinLogo } from "../market/CoinLogo";

interface HoldingsTableProps {
  holdings: Holding[];
  onEdit: (holding: Holding) => void;
  onRemove: (holding: Holding) => void;
  disabled?: boolean;
}

function quantity(value: number): string {
  return value.toLocaleString("en-US", { maximumFractionDigits: 8 });
}

export function HoldingsTable({ holdings, onEdit, onRemove, disabled = false }: HoldingsTableProps) {
  return (
    <div className="overflow-x-auto card">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <th className="px-4 py-3 font-medium">Asset</th>
            <th className="px-3 py-3 text-right font-medium">Quantity</th>
            <th className="px-3 py-3 text-right font-medium">Avg. buy price</th>
            <th className="px-3 py-3 text-right font-medium">Current price</th>
            <th className="px-3 py-3 text-right font-medium">24H</th>
            <th className="px-3 py-3 text-right font-medium">Value</th>
            <th className="px-3 py-3 text-right font-medium">P/L</th>
            <th className="px-3 py-3 text-right font-medium">Alloc.</th>
            <th className="px-3 py-3"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding) => (
            <tr key={holding.coin_id} className="border-b border-slate-50 last:border-0 dark:border-slate-800">
              <td className="px-4 py-3">
                <Link to={`/coins/${holding.coin_id}`} className="flex items-center gap-2 font-medium text-slate-800 hover:underline dark:text-slate-100">
                  <CoinLogo src={holding.logo_url} alt="" />
                  <span className="max-w-[160px] truncate">{holding.name}</span>
                  <span className="text-xs text-slate-400">{holding.symbol.toUpperCase()}</span>
                </Link>
              </td>
              <td className="px-3 py-3 text-right tabular-nums">{quantity(holding.quantity)}</td>
              <td className="px-3 py-3 text-right tabular-nums">{formatUsd(holding.average_buy_price)}</td>
              <td className="px-3 py-3 text-right tabular-nums">
                {holding.has_price ? formatUsd(holding.current_price) : <span className="text-slate-400">No price</span>}
                {holding.price_is_stale && <span className="block text-[10px] text-amber-600 dark:text-amber-400">may be out of date</span>}
              </td>
              <td className="px-3 py-3 text-right"><ChangeBadge value={holding.percent_change_24h} /></td>
              <td className="px-3 py-3 text-right tabular-nums">{formatUsd(holding.current_value)}</td>
              <td className={`px-3 py-3 text-right tabular-nums ${changeColorClass(holding.unrealized_pnl)}`}>
                {holding.unrealized_pnl === null ? "N/A" : `${holding.unrealized_pnl > 0 ? "+" : ""}${formatUsd(holding.unrealized_pnl)}`}
                <span className="block text-xs">{formatPercent(holding.unrealized_pnl_pct)}</span>
              </td>
              <td className="px-3 py-3 text-right tabular-nums text-slate-500">
                {holding.allocation_pct === null ? "—" : `${holding.allocation_pct.toFixed(1)}%`}
              </td>
              <td className="px-3 py-3 text-right whitespace-nowrap">
                <button type="button" onClick={() => onEdit(holding)} disabled={disabled} aria-label={`Edit ${holding.name} holding`} className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-40 dark:hover:bg-slate-800">
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                </button>
                <button type="button" onClick={() => onRemove(holding)} disabled={disabled} aria-label={`Remove ${holding.name} from portfolio`} className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-40 dark:hover:bg-slate-800">
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
