import { useState } from "react";
import { X } from "lucide-react";

import { useCoinSearch } from "../../hooks/useCoinSearch";
import type { CoinSearchResult } from "../../types/coin";
import { formatUsd } from "../../utils/formatters";
import { CoinLogo } from "../market/CoinLogo";

/** The minimum a form needs to know about a chosen coin. */
export type PickedCoin = Pick<CoinSearchResult, "id" | "name" | "symbol" | "logo_url">;

interface CoinPickerProps {
  selected: PickedCoin | null;
  onSelect: (coin: CoinSearchResult | null) => void;
  disabled?: boolean;
  label?: string;
}

/** Search-as-you-type coin chooser backed by the real /coins/search endpoint (no local/sample coin list). */
export function CoinPicker({ selected, onSelect, disabled = false, label = "Coin" }: CoinPickerProps) {
  const [query, setQuery] = useState("");
  const search = useCoinSearch(query, 6, selected === null);

  if (selected) {
    return (
      <div>
        <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
        <div className="flex items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900">
          <span className="flex items-center gap-2 text-sm text-slate-900 dark:text-slate-100">
            <CoinLogo src={selected.logo_url} alt="" size={20} />
            {selected.name} <span className="text-slate-400">{selected.symbol.toUpperCase()}</span>
          </span>
          {!disabled && (
            <button type="button" onClick={() => onSelect(null)} aria-label="Choose a different coin" className="rounded p-0.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <label htmlFor="coin-picker-input" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
        {label}
      </label>
      <input
        id="coin-picker-input"
        type="text"
        value={query}
        disabled={disabled}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search by name or symbol..."
        autoComplete="off"
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-sky-500 focus:ring-1 focus:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      />
      {search.hasQuery && (
        <div className="mt-1 rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900" role="listbox" aria-label="Coin results">
          {search.loading && <p className="px-3 py-2 text-xs text-slate-500">Searching...</p>}
          {!search.loading && search.error && <p className="px-3 py-2 text-xs text-red-600 dark:text-red-400">{search.error}</p>}
          {!search.loading && !search.error && search.results.length === 0 && (
            <p className="px-3 py-2 text-xs text-slate-500">No coins match &ldquo;{query.trim()}&rdquo;.</p>
          )}
          {!search.loading &&
            search.results.map((coin) => (
              <button
                key={coin.id}
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => {
                  onSelect(coin);
                  setQuery("");
                }}
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50 focus:bg-slate-50 focus:outline-none dark:hover:bg-slate-800 dark:focus:bg-slate-800"
              >
                <span className="flex items-center gap-2 text-slate-900 dark:text-slate-100">
                  <CoinLogo src={coin.logo_url} alt="" size={20} />
                  {coin.name} <span className="text-slate-400">{coin.symbol.toUpperCase()}</span>
                </span>
                <span className="text-xs tabular-nums text-slate-500">{formatUsd(coin.price_usd)}</span>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
