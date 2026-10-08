import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { Loader } from "../components/common/Loader";
import { Pagination } from "../components/common/Pagination";
import { RetryError } from "../components/common/RetryError";
import { CoinFilter } from "../components/news/CoinFilter";
import { NewsCard } from "../components/news/NewsCard";
import { NewsFeedNotice } from "../components/news/NewsFeedNotice";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { useNewsList } from "../hooks/useNewsList";
import { fetchNewsSources } from "../services/api/news.api";
import type { SentimentLabel } from "../types/news";

const PAGE_SIZE = 20;
const SENTIMENTS: SentimentLabel[] = ["positive", "neutral", "negative"];

function parsePage(value: string | null): number {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

const fieldClass =
  "rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

/**
 * Global crypto news feed. All filtering (coin, source, sentiment, dates,
 * text) and pagination happen on the backend; the filters live in the URL,
 * so a filtered view is shareable and the Back button works.
 */
export function News() {
  const [params, setParams] = useSearchParams();

  const page = parsePage(params.get("page"));
  const coinId = params.get("coin") || undefined;
  const source = params.get("source") || "";
  const sentimentParam = params.get("sentiment");
  const sentiment = SENTIMENTS.find((value) => value === sentimentParam);
  const from = DATE_RE.test(params.get("from") ?? "") ? (params.get("from") as string) : "";
  const to = DATE_RE.test(params.get("to") ?? "") ? (params.get("to") as string) : "";
  const urlSearch = params.get("q") ?? "";

  const updateParams = useCallback(
    (patch: Record<string, string | undefined>, keepPage = false) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [key, value] of Object.entries(patch)) {
            if (value) next.set(key, value);
            else next.delete(key);
          }
          if (!keepPage && !("page" in patch)) next.delete("page");
          return next;
        },
        { replace: true }
      );
    },
    [setParams]
  );

  // Text search is debounced into the URL (one backend request per pause, not per keystroke).
  const [searchInput, setSearchInput] = useState(urlSearch);
  const debouncedSearch = useDebouncedValue(searchInput, 300).trim();
  useEffect(() => {
    if (debouncedSearch !== urlSearch) updateParams({ q: debouncedSearch || undefined });
    // Only react to the debounced value changing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const [sources, setSources] = useState<string[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    fetchNewsSources(controller.signal)
      .then((response) => setSources(response.items))
      .catch(() => setSources([])); // the source filter simply stays empty; the feed itself is unaffected
    return () => controller.abort();
  }, []);

  const { data, loading, refreshing, error, retry } = useNewsList({
    page,
    limit: PAGE_SIZE,
    coinId,
    search: urlSearch,
    source,
    sentiment,
    dateFrom: from ? `${from}T00:00:00Z` : undefined,
    dateTo: to ? `${to}T23:59:59.999Z` : undefined,
  });

  const filtersActive = Boolean(coinId || source || sentiment || from || to || urlSearch);
  const clearFilters = () => {
    setSearchInput("");
    setParams(new URLSearchParams(), { replace: true });
  };

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Crypto News</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
          Latest headlines from cryptocurrency news publishers. Sentiment labels describe the tone of an article — they are not
          price predictions or advice.
        </p>
      </div>

      <form
        role="search"
        aria-label="Filter news"
        onSubmit={(event) => event.preventDefault()}
        className="mb-4 flex flex-wrap items-center gap-2"
      >
        <div>
          <label className="sr-only" htmlFor="news-search">
            Search headlines
          </label>
          <input
            id="news-search"
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search headlines…"
            maxLength={100}
            className={`${fieldClass} w-56 placeholder:text-slate-400`}
          />
        </div>

        <CoinFilter coinId={coinId} onChange={(value) => updateParams({ coin: value })} />

        <div>
          <label className="sr-only" htmlFor="news-source">
            Source
          </label>
          <select
            id="news-source"
            value={source}
            onChange={(event) => updateParams({ source: event.target.value || undefined })}
            className={fieldClass}
          >
            <option value="">All sources</option>
            {/* Keep a URL-supplied source selectable even if the sources request failed or it isn't listed. */}
            {source && !sources.includes(source) && <option value={source}>{source}</option>}
            {sources.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="sr-only" htmlFor="news-sentiment">
            Sentiment
          </label>
          <select
            id="news-sentiment"
            value={sentiment ?? ""}
            onChange={(event) => updateParams({ sentiment: event.target.value || undefined })}
            className={fieldClass}
          >
            <option value="">Any sentiment</option>
            <option value="positive">Positive</option>
            <option value="neutral">Neutral</option>
            <option value="negative">Negative</option>
          </select>
        </div>

        <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
          <label htmlFor="news-from">From</label>
          <input id="news-from" type="date" value={from} max={to || undefined} onChange={(e) => updateParams({ from: e.target.value || undefined })} className={fieldClass} />
          <label htmlFor="news-to">to</label>
          <input id="news-to" type="date" value={to} min={from || undefined} onChange={(e) => updateParams({ to: e.target.value || undefined })} className={fieldClass} />
          <span className="hidden sm:inline">(UTC)</span>
        </div>

        {filtersActive && (
          <button
            type="button"
            onClick={clearFilters}
            className="text-sm font-medium text-sky-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:text-sky-400"
          >
            Clear filters
          </button>
        )}
      </form>

      {data && <NewsFeedNotice status={data.status} />}

      {loading && <Loader label="Loading news..." />}

      {error && !data && (
        <div>
          {coinId && (error.kind === "not_found" || error.kind === "invalid") ? (
            <div className="space-y-2" role="alert">
              <ErrorMessage message={error.message} />
              <button
                type="button"
                onClick={() => updateParams({ coin: undefined })}
                className="text-sm font-medium text-sky-700 hover:underline dark:text-sky-400"
              >
                Clear coin filter
              </button>
            </div>
          ) : (
            <RetryError message={error.message} onRetry={retry} />
          )}
        </div>
      )}

      {error && data && (
        <div className="mb-3">
          <RetryError compact message={`Could not refresh the list: ${error.message}`} onRetry={retry} />
        </div>
      )}

      {data && data.items.length === 0 && !error && (
        <EmptyState
          message={
            filtersActive
              ? "No articles match these filters."
              : "No news articles are stored yet. News is collected in the background — check back in a few minutes."
          }
          action={
            filtersActive ? (
              <button type="button" onClick={clearFilters} className="text-sm font-medium text-sky-700 hover:underline dark:text-sky-400">
                Clear filters
              </button>
            ) : undefined
          }
        />
      )}

      {data && data.items.length > 0 && (
        <section aria-label="News articles" aria-busy={refreshing}>
          <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
            {data.total.toLocaleString("en-US")} article{data.total === 1 ? "" : "s"}
            {refreshing ? " — updating…" : ""}
          </p>
          <ul className={`space-y-3 ${refreshing ? "opacity-60" : ""}`}>
            {data.items.map((article) => (
              <li key={article.news_id}>
                <NewsCard article={article} />
              </li>
            ))}
          </ul>
          <Pagination
            page={data.page}
            pages={data.pages}
            disabled={refreshing}
            label="news"
            onPageChange={(next) => {
              updateParams({ page: next > 1 ? String(next) : undefined }, true);
              window.scrollTo?.({ top: 0 });
            }}
          />
        </section>
      )}
    </AppShell>
  );
}
