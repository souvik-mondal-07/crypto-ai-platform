import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { watchlistApi } from "../../services/api/watchlist.api";
import { useWatchlistStore } from "../../store/watchlistStore";
import type { WatchlistItem } from "../../types/userFeatures";
import { toErrorMessage } from "../../utils/apiErrors";
import { formatUsd } from "../../utils/formatters";
import { ChangeBadge } from "../common/ChangeBadge";
import { RetryError } from "../common/RetryError";
import { SectionHeading } from "../common/SectionHeading";
import { CoinLogo } from "../market/CoinLogo";
import { Skeleton } from "../ui/Skeleton";

const LIMIT = 6;

/**
 * The signed-in user's watched coins with current prices — real backend data from /watchlist (the same list
 * shown on the Watchlist page), never sample coins. Re-reads when the user adds/removes a coin elsewhere.
 */
export function WatchedCoins() {
  const idsKey = useWatchlistStore((state) => state.ids.join(","));
  const [items, setItems] = useState<WatchlistItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    watchlistApi
      .list(1, LIMIT)
      .then((response) => {
        if (!cancelled) setItems(response.items);
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(toErrorMessage(caught, "Your watchlist could not be loaded."));
      });
    return () => {
      cancelled = true;
    };
  }, [attempt, idsKey]);

  return (
    <section id="watched-coins" aria-labelledby="watched-coins-heading" className="card card-pad h-full scroll-mt-24">
      <SectionHeading
        id="watched-coins-heading"
        title="Watchlist"
        actions={
          <Link to="/watchlist" className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:underline dark:text-sky-400">
            View All <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        }
      />

      {error ? (
        <RetryError message={error} onRetry={() => setAttempt((value) => value + 1)} compact />
      ) : items === null ? (
        <div className="space-y-3" aria-hidden="true">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="h-6 w-6 rounded-full" />
              <Skeleton className="h-3 flex-1" />
              <Skeleton className="h-3 w-16" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          Star coins on Markets or Coin Details to track them here.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {items.map((item) => (
            <li key={item.coin_id}>
              <Link
                to={`/coins/${item.coin_id}`}
                className="flex items-center gap-3 rounded-md px-1 py-2 hover:bg-slate-50 dark:hover:bg-slate-800/60"
              >
                <CoinLogo src={item.logo_url} alt="" size={24} />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800 dark:text-slate-100">{item.name}</span>
                <span className="text-sm tabular-nums text-slate-700 dark:text-slate-200">{formatUsd(item.price_usd)}</span>
                <ChangeBadge value={item.percent_change_24h} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
