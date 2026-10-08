import { useEffect, useId, useMemo, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDownRight, ArrowUpRight, GitCompare, LayoutDashboard, LineChart, Search, Star, type LucideIcon } from "lucide-react";

import { useCoinSearch } from "../../hooks/useCoinSearch";
import { SearchResultRow } from "./SearchResultRow";

interface PaletteAction {
  id: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  to: string;
}

/**
 * Only destinations that really exist. "Search coin" isn't a list entry — it
 * is what typing in the box does. Watchlist and Compare are modes of the
 * Markets page (see pages/Markets.tsx), not separate routes.
 */
const ACTIONS: PaletteAction[] = [
  { id: "dashboard", label: "Open Dashboard", hint: "Market overview", icon: LayoutDashboard, to: "/dashboard" },
  { id: "markets", label: "Open Markets", hint: "Explore all coins", icon: LineChart, to: "/markets" },
  { id: "watchlist", label: "Open Watchlist", hint: "Your starred coins", icon: Star, to: "/markets?tab=watchlist" },
  { id: "compare", label: "Compare coins", hint: "Side-by-side metrics", icon: GitCompare, to: "/markets?compare=1" },
  { id: "gainers", label: "View Gainers", hint: "Top 24H risers", icon: ArrowUpRight, to: "/markets?tab=gainers" },
  { id: "losers", label: "View Losers", hint: "Top 24H fallers", icon: ArrowDownRight, to: "/markets?tab=losers" },
];

type Item = { kind: "action"; action: PaletteAction } | { kind: "coin"; index: number };

/**
 * Ctrl/⌘+K command palette. Mounted once in the Header. Dependency-free: a
 * plain modal dialog with a focus-on-open input, Esc to close, ↑/↓/Enter to
 * pick, and click-outside to dismiss.
 */
export function CommandPalette() {
  const navigate = useNavigate();
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const { results, loading, error, hasQuery, settledQuery, retry } = useCoinSearch(query, 6, open);

  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const items: Item[] = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const actions = ACTIONS.filter((action) => !needle || action.label.toLowerCase().includes(needle));
    return [
      ...actions.map((action): Item => ({ kind: "action", action })),
      ...results.map((_, index): Item => ({ kind: "coin", index })),
    ];
  }, [query, results]);

  useEffect(() => {
    setActive((current) => Math.min(current, Math.max(items.length - 1, 0)));
  }, [items.length]);

  function run(item: Item | undefined) {
    if (!item) return;
    setOpen(false);
    if (item.kind === "action") navigate(item.action.to);
    else navigate(`/coins/${results[item.index].id}`);
  }

  function onInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((value) => (items.length ? (value + 1) % items.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => (items.length ? (value <= 0 ? items.length - 1 : value - 1) : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      run(items[active]);
    }
  }

  if (!open) return null;

  const optionId = (index: number) => `${listId}-${index}`;
  const stillTyping = hasQuery && settledQuery !== query.trim();

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/50 px-4 pt-[12vh]" onMouseDown={() => setOpen(false)}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onMouseDown={(event) => event.stopPropagation()}
        className="w-full max-w-lg overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex items-center gap-2 border-b border-slate-200 px-3 py-2.5 dark:border-slate-800">
          <Search className="h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            // A modal dialog should take keyboard focus the moment it opens.
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
            value={query}
            onChange={(event) => { setQuery(event.target.value); setActive(0); }}
            onKeyDown={onInputKeyDown}
            placeholder="Search a coin or run an action…"
            aria-label="Search a coin or run an action"
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={items.length ? optionId(active) : undefined}
            autoComplete="off"
            className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100"
          />
          <kbd className="rounded border border-slate-300 px-1 text-[10px] text-slate-500 dark:border-slate-600 dark:text-slate-400">Esc</kbd>
        </div>

        <ul id={listId} role="listbox" aria-label="Results" className="max-h-[50vh] overflow-y-auto py-1">
          {items.map((item, index) =>
            item.kind === "action" ? (
              <li
                key={item.action.id}
                id={optionId(index)}
                role="option"
                aria-selected={index === active}
                onMouseEnter={() => setActive(index)}
                onMouseDown={(event) => { event.preventDefault(); run(item); }}
                className={`flex cursor-pointer items-center gap-3 px-3 py-2 ${index === active ? "bg-sky-50 dark:bg-slate-800" : ""}`}
              >
                <item.action.icon className="h-4 w-4 text-slate-500 dark:text-slate-400" aria-hidden="true" />
                <span className="flex-1 text-sm text-slate-800 dark:text-slate-100">{item.action.label}</span>
                <span className="text-xs text-slate-400">{item.action.hint}</span>
              </li>
            ) : (
              <SearchResultRow
                key={results[item.index].id}
                id={optionId(index)}
                coin={results[item.index]}
                active={index === active}
                onSelect={() => run(item)}
                onHover={() => setActive(index)}
              />
            )
          )}
        </ul>

        {(loading || stillTyping) && <p role="status" className="px-3 pb-3 text-xs text-slate-500 dark:text-slate-400">Searching coins…</p>}
        {!loading && !stillTyping && error && (
          <p role="alert" className="px-3 pb-3 text-xs text-red-600 dark:text-red-400">
            {error}{" "}
            <button type="button" onClick={retry} className="font-medium underline">Retry</button>
          </p>
        )}
        {!loading && !stillTyping && !error && hasQuery && results.length === 0 && (
          <p role="status" className="px-3 pb-3 text-xs text-slate-500 dark:text-slate-400">No coins match &ldquo;{query.trim()}&rdquo;.</p>
        )}
      </div>
    </div>
  );
}
