import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../components/common/EmptyState";
import { TableSkeleton } from "../components/ui/Skeleton";
import { RetryError } from "../components/common/RetryError";
import { AppShell } from "../components/layout/AppShell";
import { WatchlistTable } from "../components/watchlist/WatchlistTable";
import { useWatchlist } from "../hooks/useWatchlist";
import { watchlistApi } from "../services/api/watchlist.api";
import type { WatchlistItem } from "../types/userFeatures";
import { toErrorMessage } from "../utils/apiErrors";

/** /watchlist — the signed-in user's watched coins with live market data. */
export function Watchlist() {
  const { ids, remove, pending } = useWatchlist();
  const [items, setItems] = useState<WatchlistItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    watchlistApi
      .list(1, 250)
      .then((response) => {
        if (!cancelled) setItems(response.items);
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(toErrorMessage(caught, "Your watchlist could not be loaded."));
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setItems(null);
    setAttempt((value) => value + 1);
  }, []);

  // A removal is reflected immediately (the store drops the id before the server confirms).
  const visible = items === null ? null : items.filter((item) => ids.includes(item.coin_id) || pending.includes(item.coin_id));

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Watchlist</h1>
          <p className="page-subtitle">Coins you are tracking, with current market data.</p>
        </div>
      </div>


      <div className="mt-6">
        {error ? (
          <RetryError message={error} onRetry={retry} />
        ) : visible === null ? (
          <TableSkeleton label="Loading your watchlist..." rows={5} cols={5} />
        ) : visible.length === 0 ? (
          <EmptyState
            message="Your watchlist is empty. Add coins from the Markets or Coin Details page."
            action={
              <Link to="/markets" className="text-sm font-medium text-sky-600 hover:underline dark:text-sky-400">
                Browse Markets
              </Link>
            }
          />
        ) : (
          <WatchlistTable items={visible} pending={pending} onRemove={(item) => void remove(item.coin_id, item.name)} />
        )}
      </div>
    </AppShell>
  );
}
