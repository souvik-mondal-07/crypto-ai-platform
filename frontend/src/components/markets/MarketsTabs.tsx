import { MARKET_TABS, type MarketTabKey } from "../../utils/marketFilters";

interface MarketsTabsProps {
  active: MarketTabKey;
  onChange: (key: MarketTabKey) => void;
  watchlistCount: number;
}

/** Category tabs — every tab is backed by a real server-side view (see utils/marketFilters.ts). */
export function MarketsTabs({ active, onChange, watchlistCount }: MarketsTabsProps) {
  return (
    <div role="tablist" aria-label="Market categories" className="flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-800">
      {MARKET_TABS.map((tab) => {
        const selected = tab.key === active;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.key)}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
              selected
                ? "border-sky-600 text-sky-700 dark:border-sky-400 dark:text-sky-300"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            {tab.label}
            {tab.key === "watchlist" && watchlistCount > 0 && (
              <span className="ml-1.5 rounded-full bg-slate-200 px-1.5 text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-200">{watchlistCount}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
