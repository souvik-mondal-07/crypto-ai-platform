import { useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";

import { useCoinSearch } from "../../hooks/useCoinSearch";
import { SearchResultRow } from "./SearchResultRow";

/**
 * Header search with live suggestions.
 *
 * Preserves the original behaviour: submitting the form (Enter with nothing
 * highlighted) goes to `/markets?q=...`, which the Markets page picks up.
 * Added: suggestions from the real search endpoint, ↑/↓ to move, Enter to open
 * the highlighted coin, Esc to close, loading / no-results / error states, and
 * combobox ARIA wiring for screen readers.
 */
export function GlobalSearch() {
  const navigate = useNavigate();
  const listId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const { results, loading, error, hasQuery, settledQuery, retry } = useCoinSearch(query, 8);
  const showPanel = open && query.trim() !== "";
  const optionId = (index: number) => `${listId}-option-${index}`;

  function close() {
    setOpen(false);
    setActiveIndex(-1);
  }

  function openCoin(coinId: string) {
    close();
    setQuery("");
    navigate(`/coins/${coinId}`);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      if (open) {
        event.preventDefault();
        close();
      }
      return;
    }
    if (!showPanel || results.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? results.length - 1 : index - 1));
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const highlighted = activeIndex >= 0 ? results[activeIndex] : undefined;
    if (highlighted) {
      openCoin(highlighted.id);
      return;
    }
    const trimmed = query.trim();
    if (trimmed) {
      close();
      navigate(`/markets?q=${encodeURIComponent(trimmed)}`);
    }
  }

  const stillTyping = hasQuery && settledQuery !== query.trim();

  return (
    <form
      role="search"
      onSubmit={handleSubmit}
      className="relative ml-auto flex min-w-0 flex-1 items-center gap-1.5 sm:max-w-xs"
    >
      <div className="flex w-full items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 focus-within:ring-2 focus-within:ring-sky-500 dark:border-slate-700 dark:bg-slate-900">
        <Search className="h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={close}
          onKeyDown={handleKeyDown}
          placeholder="Search coins..."
          aria-label="Search coins"
          role="combobox"
          aria-expanded={showPanel}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? optionId(activeIndex) : undefined}
          autoComplete="off"
          className="w-full min-w-0 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400 dark:text-slate-200"
        />
        <kbd className="hidden flex-shrink-0 rounded border border-slate-300 px-1 text-[10px] text-slate-500 dark:border-slate-600 dark:text-slate-400 lg:inline" title="Open the command palette">
          Ctrl K
        </kbd>
      </div>

      {showPanel && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 min-w-[18rem] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900 sm:min-w-[22rem]">
          <ul id={listId} role="listbox" aria-label="Coin suggestions" className="max-h-80 overflow-y-auto">
            {results.map((coin, index) => (
              <SearchResultRow
                key={coin.id}
                id={optionId(index)}
                coin={coin}
                active={index === activeIndex}
                onSelect={() => openCoin(coin.id)}
                onHover={() => setActiveIndex(index)}
              />
            ))}
          </ul>

          {(loading || stillTyping) && results.length === 0 && (
            <p role="status" className="px-3 py-3 text-sm text-slate-500 dark:text-slate-400">Searching…</p>
          )}
          {!loading && !stillTyping && error && (
            <div role="alert" className="flex items-center justify-between gap-2 px-3 py-3 text-sm text-red-600 dark:text-red-400">
              <span>{error}</span>
              <button type="button" onMouseDown={(event) => { event.preventDefault(); retry(); }} className="font-medium underline">
                Retry
              </button>
            </div>
          )}
          {!loading && !stillTyping && !error && hasQuery && results.length === 0 && (
            <p role="status" className="px-3 py-3 text-sm text-slate-500 dark:text-slate-400">No coins match &ldquo;{query.trim()}&rdquo;.</p>
          )}

          <p className="border-t border-slate-100 px-3 py-1.5 text-[11px] text-slate-400 dark:border-slate-800">
            ↑ ↓ navigate · Enter open · Esc close
          </p>
        </div>
      )}
    </form>
  );
}
