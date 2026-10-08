import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { useCoinSearch } from "../../hooks/useCoinSearch";
import { fetchCoinById } from "../../services/api/coins.api";

interface CoinFilterProps {
  coinId: string | undefined;
  onChange: (coinId: string | undefined) => void;
}

/** Filter the feed to one coin. Search runs on the backend (/coins/search); nothing is matched locally. */
export function CoinFilter({ coinId, onChange }: CoinFilterProps) {
  const [query, setQuery] = useState("");
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const { results, loading, hasQuery } = useCoinSearch(query, 6, !coinId);

  // Resolve a coin id that came from the URL into a readable name (best effort — the id is the source of truth).
  useEffect(() => {
    if (!coinId) {
      setSelectedLabel(null);
      return;
    }
    let cancelled = false;
    fetchCoinById(coinId)
      .then((coin) => !cancelled && setSelectedLabel(`${coin.name} (${coin.symbol})`))
      .catch(() => !cancelled && setSelectedLabel(null));
    return () => {
      cancelled = true;
    };
  }, [coinId]);

  if (coinId) {
    return (
      <div className="flex items-center gap-1 rounded-lg border border-sky-200 bg-sky-50 px-2.5 py-1.5 text-sm text-sky-900 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-200">
        <span>Coin: {selectedLabel ?? "selected coin"}</span>
        <button
          type="button"
          onClick={() => onChange(undefined)}
          aria-label="Clear coin filter"
          className="rounded p-0.5 hover:bg-sky-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:hover:bg-sky-900"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <label className="sr-only" htmlFor="news-coin-filter">
        Filter by coin
      </label>
      <input
        id="news-coin-filter"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Filter by coin…"
        autoComplete="off"
        className="w-44 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      />
      {hasQuery && (
        <ul
          aria-label="Coin suggestions"
          className="absolute left-0 top-full z-20 mt-1 max-h-60 w-64 overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900"
        >
          {loading && <li className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">Searching…</li>}
          {!loading && results.length === 0 && (
            <li className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">No matching coins.</li>
          )}
          {results.map((coin) => (
            <li key={coin.id}>
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  onChange(coin.id);
                }}
                className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm text-slate-800 hover:bg-slate-100 focus:bg-slate-100 focus:outline-none dark:text-slate-100 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
              >
                <span className="truncate">{coin.name}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">{coin.symbol}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
