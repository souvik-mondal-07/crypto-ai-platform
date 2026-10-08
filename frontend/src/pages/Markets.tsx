import { useEffect, useMemo, useState } from "react";
import { GitCompare, Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { CoinTable } from "../components/market/CoinTable";
import { FreshnessBadge } from "../components/common/FreshnessBadge";
import { ColumnSelector } from "../components/markets/ColumnSelector";
import { ComparePanel } from "../components/markets/ComparePanel";
import { FilterPanel } from "../components/markets/FilterPanel";
import { MarketsTable } from "../components/markets/MarketsTable";
import { MarketsTabs } from "../components/markets/MarketsTabs";
import { useMarketCoins } from "../hooks/useMarketCoins";
import { useMarketSearch } from "../hooks/useMarketSearch";
import { useTrendingCoinIds } from "../hooks/useTrendingCoinIds";
import { MAX_COMPARE, useUserListsStore } from "../store/userListsStore";
import { useMarketStore } from "../store/marketStore";
import { COLUMNS, DEFAULT_VISIBLE, sanitizeVisible, type ColumnKey } from "../utils/marketColumns";
import {
  DEFAULT_SELECTION,
  MARKET_TABS,
  activeFilterCount,
  isMarketTabKey,
  parseCap,
  selectionToFilters,
  type FilterSelection,
  type MarketTabKey,
} from "../utils/marketFilters";
import { readJson, userKey, writeJson } from "../utils/userStorage";

const PAGE_SIZES = [10, 25, 50, 100];
/** Backend limit on `coin_ids` per request. */
const MAX_ID_SET = 100;
const COLUMNS_KEY = "market_columns";

/**
 * Markets — "Explore the entire cryptocurrency universe."
 *
 * The explorer: search, category tabs, server-side filters and sorting,
 * paginated table, customisable columns, watchlist and comparison. It has no
 * global-snapshot, chart, heatmap or movers sections — those are the
 * Dashboard's job.
 *
 * The tab and any `cap` preset come from the URL, so Dashboard shortcuts and
 * Ctrl+K actions can deep-link here. Every view change is ONE backend request
 * (`setView`), and the initial load is applied here rather than by the hook so
 * the first visit doesn't fire a default request followed by a filtered one.
 */
export function Markets() {
  const [searchParams, setSearchParams] = useSearchParams();

  const tabParam = searchParams.get("tab");
  const tab: MarketTabKey = isMarketTabKey(tabParam) ? tabParam : "all";
  const capParam = searchParams.get("cap");
  const compareParam = searchParams.get("compare");
  const qParam = searchParams.get("q");

  const [selection, setSelection] = useState<FilterSelection>(() =>
    capParam !== null ? { ...DEFAULT_SELECTION, cap: parseCap(capParam) } : DEFAULT_SELECTION
  );
  const [showCompare, setShowCompare] = useState(compareParam === "1");
  const [limitNotice, setLimitNotice] = useState<string | null>(null);

  const userId = useUserListsStore((state) => state.userId);
  const watchlist = useUserListsStore((state) => state.watchlist);
  const compare = useUserListsStore((state) => state.compare);
  const toggleWatchlist = useUserListsStore((state) => state.toggleWatchlist);
  const toggleCompare = useUserListsStore((state) => state.toggleCompare);
  const removeCompare = useUserListsStore((state) => state.removeCompare);
  const clearCompare = useUserListsStore((state) => state.clearCompare);

  const search = useMarketSearch();
  const fetchOverview = useMarketStore((state) => state.fetchMarketOverview);
  const overview = useMarketStore((state) => state.marketOverview);
  const coinsState = useMarketCoins({ autoLoad: false });
  const { setView, setSort, setPageSize, goToPage, refetch } = coinsState;
  const trending = useTrendingCoinIds(tab === "trending");

  // ---- visible columns (device-local, per user) ----
  const [visible, setVisible] = useState<ColumnKey[]>(DEFAULT_VISIBLE);
  useEffect(() => {
    setVisible(sanitizeVisible(readJson<unknown>(userKey(COLUMNS_KEY, userId), null)));
  }, [userId]);

  function toggleColumn(key: ColumnKey) {
    const next = visible.includes(key) ? visible.filter((item) => item !== key) : COLUMNS.map((c) => c.key).filter((k) => k === key || visible.includes(k));
    if (next.length === 0) return; // keep at least one data column
    setVisible(next);
    writeJson(userKey(COLUMNS_KEY, userId), next);
  }
  function resetColumns() {
    setVisible(DEFAULT_VISIBLE);
    writeJson(userKey(COLUMNS_KEY, userId), DEFAULT_VISIBLE);
  }

  // ---- header: universe size (one non-polled request) ----
  useEffect(() => {
    fetchOverview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- consume one-shot URL hand-offs (?cap=, ?compare=1) ----
  useEffect(() => {
    if (capParam === null && compareParam === null) return;
    if (capParam !== null) {
      const cap = parseCap(capParam);
      setSelection((current) => (current.cap === cap ? current : { ...DEFAULT_SELECTION, cap }));
    }
    if (compareParam === "1") setShowCompare(true);
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.delete("cap");
        next.delete("compare");
        return next;
      },
      { replace: true }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [capParam, compareParam]);

  // ---- header search hand-off (?q=) ----
  useEffect(() => {
    if (qParam !== null && qParam !== search.searchQuery) search.setSearchQuery(qParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qParam]);

  // ---- apply the tab + filters: exactly one request per change ----
  const watchlistKey = watchlist.slice(0, MAX_ID_SET).join(",");
  const trendingKey = trending.ids.slice(0, MAX_ID_SET).join(",");
  const filtersKey = JSON.stringify(selection);

  useEffect(() => {
    const config = MARKET_TABS.find((candidate) => candidate.key === tab) ?? MARKET_TABS[0];
    let coinIds: string[] | null = null;
    if (tab === "watchlist") coinIds = watchlist.slice(0, MAX_ID_SET);
    if (tab === "trending") {
      if (trending.loading) return; // wait for the id set rather than load "all" first
      coinIds = trending.ids.slice(0, MAX_ID_SET);
    }
    setView({
      filter: config.filter,
      sortBy: config.sortBy,
      sortDirection: config.sortDirection,
      filters: selectionToFilters(selection),
      coinIds,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, filtersKey, tab === "watchlist" ? watchlistKey : "", tab === "trending" ? trendingKey : "", tab === "trending" ? trending.loading : false]);

  function changeTab(key: MarketTabKey) {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (key === "all") next.delete("tab");
        else next.set("tab", key);
        return next;
      },
      { replace: false }
    );
  }

  function handleFilterChange(next: FilterSelection) {
    setSelection(next);
    // The tab/filters effect above issues the request.
  }

  function handleToggleCompare(coinId: string) {
    const ok = toggleCompare(coinId);
    setLimitNotice(ok ? null : `You can compare up to ${MAX_COMPARE} coins at a time.`);
    if (ok && !showCompare && compare.length + 1 >= 2) setShowCompare(true);
  }

  const universeCoins = overview?.active_cryptocurrencies ?? null;
  const withMarketData = coinsState.universeTotal;

  const emptyMessage = useMemo(() => {
    if (tab === "watchlist") return "Your watchlist is empty. Star coins in the table to track them here.";
    if (tab === "trending") {
      if (!trending.available) return "Trending coins aren't available from the current data provider.";
      return "No trending coins match the synced market data right now.";
    }
    return activeFilterCount(selection) > 0
      ? "No coins match these filters. Try widening or clearing them."
      : "No market data available yet.";
  }, [tab, trending.available, selection]);

  const tableError = tab === "trending" && trending.error ? trending.error : coinsState.error;
  const retryTable = tab === "trending" && trending.error ? trending.retry : refetch;
  const tableLoading = coinsState.loading || (tab === "trending" && trending.loading);

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Cryptocurrency Markets</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Explore and analyze the synchronized cryptocurrency market.</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {universeCoins !== null && <span>{universeCoins.toLocaleString()} coins tracked</span>}
            {universeCoins !== null && withMarketData != null && <span aria-hidden="true"> · </span>}
            {withMarketData != null && <span>{withMarketData.toLocaleString()} with market data</span>}
          </p>
        </div>
        <FreshnessBadge lastUpdated={coinsState.lastUpdated} isStale={coinsState.isStale} />
      </div>

      {coinsState.isStale && (
        <p role="status" className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
          Market data hasn&apos;t been refreshed recently, so prices shown may be out of date.
        </p>
      )}

      <div className="mt-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm focus-within:ring-2 focus-within:ring-sky-500 dark:border-slate-800 dark:bg-slate-900 lg:max-w-md lg:flex-1">
          <Search className="h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden="true" />
          <input
            type="text"
            value={search.searchQuery}
            onChange={(e) => search.setSearchQuery(e.target.value)}
            placeholder="Search by name, symbol, or coin ID..."
            aria-label="Search cryptocurrencies"
            className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100"
          />
        </div>

        {!search.isSearching && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setShowCompare((value) => !value)}
              aria-pressed={showCompare}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              <GitCompare className="h-4 w-4" aria-hidden="true" />
              Compare{compare.length > 0 ? ` (${compare.length})` : ""}
            </button>
            <ColumnSelector visible={visible} onToggle={toggleColumn} onReset={resetColumns} />
            <label className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <span>Show</span>
              <select
                value={coinsState.limit}
                aria-label="Rows per page"
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                {PAGE_SIZES.map((size) => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
            </label>
          </div>
        )}
      </div>

      {limitNotice && <p role="status" className="mt-2 text-xs text-amber-700 dark:text-amber-400">{limitNotice}</p>}

      {showCompare && !search.isSearching && (
        <div className="mt-4">
          <ComparePanel coinIds={compare} onRemove={removeCompare} onClear={clearCompare} onClose={() => setShowCompare(false)} />
        </div>
      )}

      {search.isSearching ? (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <CoinTable
            coins={search.results}
            coinMarketData={{}}
            loading={search.loading}
            error={search.error}
            onRetry={search.retry}
            emptyMessage={`No coins matched "${search.searchQuery.trim()}".`}
          />
        </div>
      ) : (
        <>
          <div className="mt-4">
            <MarketsTabs active={tab} onChange={changeTab} watchlistCount={watchlist.length} />
          </div>

          <div className="mt-3">
            <FilterPanel selection={selection} onChange={handleFilterChange} />
          </div>

          <div className="mt-3 rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
            <MarketsTable
              coins={coinsState.coins}
              loading={tableLoading}
              error={tableError}
              onRetry={retryTable}
              sortBy={coinsState.sortBy}
              sortDirection={coinsState.sortDirection}
              onSort={setSort}
              page={coinsState.page}
              pages={coinsState.pages}
              total={coinsState.total}
              limit={coinsState.limit}
              onPageChange={goToPage}
              visible={visible}
              watchlist={watchlist}
              onToggleWatch={toggleWatchlist}
              compare={compare}
              onToggleCompare={handleToggleCompare}
              emptyMessage={emptyMessage}
            />
          </div>
        </>
      )}
    </AppShell>
  );
}
