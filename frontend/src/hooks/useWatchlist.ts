import { useCallback } from "react";

import { useWatchlistStore } from "../store/watchlistStore";

/** Watchlist state + actions for components. All persistence goes through the server-backed store. */
export function useWatchlist() {
  const ids = useWatchlistStore((state) => state.ids);
  const status = useWatchlistStore((state) => state.status);
  const error = useWatchlistStore((state) => state.error);
  const notice = useWatchlistStore((state) => state.notice);
  const pending = useWatchlistStore((state) => state.pending);
  const userId = useWatchlistStore((state) => state.userId);
  const toggle = useWatchlistStore((state) => state.toggle);
  const add = useWatchlistStore((state) => state.add);
  const remove = useWatchlistStore((state) => state.remove);
  const clearNotice = useWatchlistStore((state) => state.clearNotice);
  const load = useWatchlistStore((state) => state.load);

  const isWatched = useCallback((coinId: string) => ids.includes(coinId), [ids]);
  const reload = useCallback(() => load(userId), [load, userId]);

  return { ids, status, error, notice, pending, isWatched, toggle, add, remove, clearNotice, reload };
}
