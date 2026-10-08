import { useNavigate } from "react-router-dom";

import { CoinLogo } from "./CoinLogo";
import { SkeletonMoverCard } from "./Skeletons";
import { EmptyState } from "../common/EmptyState";
import { ErrorMessage } from "../common/ErrorMessage";
import { changeColorClass, formatPercent, formatUsd } from "../../utils/formatters";
import type { MoverItem } from "../../types/market";

interface MoverListProps {
  title: string;
  items: MoverItem[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  emptyMessage: string;
}

export function MoverList({ title, items, loading, error, onRetry, emptyMessage }: MoverListProps) {
  const navigate = useNavigate();

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</h3>

      {loading && (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonMoverCard key={i} />
          ))}
        </div>
      )}

      {!loading && error && (
        <div>
          <ErrorMessage message={error} />
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 text-sm font-medium text-sky-600 hover:underline dark:text-sky-400"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && items.length === 0 && <EmptyState message={emptyMessage} />}

      {!loading && !error && items.length > 0 && (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.coin_id}>
              <button
                type="button"
                onClick={() => navigate(`/coins/${item.coin_id}`)}
                className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <CoinLogo src={item.logo_url} alt={item.name} size={28} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">{item.name}</p>
                    <p className="text-xs text-slate-400">{item.symbol}</p>
                  </div>
                </div>
                <div className="flex-shrink-0 text-right">
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{formatUsd(item.price_usd)}</p>
                  <p className={`text-xs font-medium ${changeColorClass(item.percent_change_24h)}`}>
                    {formatPercent(item.percent_change_24h)}
                  </p>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
