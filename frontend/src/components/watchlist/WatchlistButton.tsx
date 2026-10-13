import { useWatchlist } from "../../hooks/useWatchlist";

interface WatchlistButtonProps {
  coinId: string;
  coinName: string;
}

/** ☆ Add to Watchlist / ★ In Watchlist — backed by the server, so it reflects the signed-in user's own list. */
export function WatchlistButton({ coinId, coinName }: WatchlistButtonProps) {
  const { isWatched, toggle, pending, status } = useWatchlist();
  const watched = isWatched(coinId);
  const busy = pending.includes(coinId);
  const unavailable = status === "loading" || status === "idle";

  return (
    <div className="flex flex-col">
      <button
        type="button"
        onClick={() => void toggle(coinId, coinName)}
        disabled={busy || unavailable}
        aria-pressed={watched}
        aria-label={watched ? `Remove ${coinName} from watchlist` : `Add ${coinName} to watchlist`}
        className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-60 ${
          watched
            ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
        }`}
      >
        <span aria-hidden="true">{watched ? "★" : "☆"}</span>
        {watched ? "In Watchlist" : "Add to Watchlist"}
      </button>
    </div>
  );
}
