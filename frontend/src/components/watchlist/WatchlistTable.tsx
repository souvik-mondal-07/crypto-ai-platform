import { Link } from "react-router-dom";
import { Trash2 } from "lucide-react";

import type { WatchlistItem } from "../../types/userFeatures";
import { formatCompactUsd, formatRelativeTime, formatUsd } from "../../utils/formatters";
import { ChangeBadge } from "../common/ChangeBadge";
import { CoinLogo } from "../market/CoinLogo";

interface WatchlistTableProps {
  items: WatchlistItem[];
  pending: string[];
  onRemove: (item: WatchlistItem) => void;
}

/** Watched coins with their CURRENT market data (read from the backend on load; nothing here is stored or invented). */
export function WatchlistTable({ items, pending, onRemove }: WatchlistTableProps) {
  return (
    <div className="overflow-x-auto card">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <th className="px-4 py-3 font-medium">Coin</th>
            <th className="px-3 py-3 font-medium">Symbol</th>
            <th className="px-3 py-3 text-right font-medium">Price</th>
            <th className="px-3 py-3 text-right font-medium">24H</th>
            <th className="px-3 py-3 text-right font-medium">Market cap</th>
            <th className="px-3 py-3 text-right font-medium">Volume (24H)</th>
            <th className="px-3 py-3 font-medium">Last updated</th>
            <th className="px-3 py-3"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.coin_id} className="border-b border-slate-50 last:border-0 dark:border-slate-800">
              <td className="px-4 py-3">
                <Link to={`/coins/${item.coin_id}`} className="flex items-center gap-2 font-medium text-slate-800 hover:underline dark:text-slate-100">
                  <CoinLogo src={item.logo_url} alt="" />
                  <span className="max-w-[180px] truncate">{item.name}</span>
                </Link>
              </td>
              <td className="px-3 py-3 text-slate-500">{item.symbol.toUpperCase()}</td>
              <td className="px-3 py-3 text-right tabular-nums">{formatUsd(item.price_usd)}</td>
              <td className="px-3 py-3 text-right"><ChangeBadge value={item.percent_change_24h} /></td>
              <td className="px-3 py-3 text-right tabular-nums">{formatCompactUsd(item.market_cap_usd)}</td>
              <td className="px-3 py-3 text-right tabular-nums">{formatCompactUsd(item.volume_24h_usd)}</td>
              <td className="px-3 py-3 text-xs text-slate-500 dark:text-slate-400">
                {formatRelativeTime(item.last_updated)}
                {item.is_stale && <span className="ml-1 text-amber-600 dark:text-amber-400">(may be out of date)</span>}
              </td>
              <td className="px-3 py-3 text-right">
                <button
                  type="button"
                  onClick={() => onRemove(item)}
                  disabled={pending.includes(item.coin_id)}
                  aria-label={`Remove ${item.name} from watchlist`}
                  className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-40 dark:hover:bg-slate-800"
                >
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
