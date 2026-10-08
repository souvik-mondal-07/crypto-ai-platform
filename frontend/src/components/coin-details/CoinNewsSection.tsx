import { useState } from "react";
import { Link } from "react-router-dom";

import { useNewsList } from "../../hooks/useNewsList";
import { EmptyState } from "../common/EmptyState";
import { Loader } from "../common/Loader";
import { Pagination } from "../common/Pagination";
import { RetryError } from "../common/RetryError";
import { NewsCard } from "../news/NewsCard";
import { NewsFeedNotice } from "../news/NewsFeedNotice";

const PAGE_SIZE = 5;

/**
 * Latest news for this coin. Relevance is decided by the backend (articles are
 * associated with coins at ingestion from the provider's own coin tags) — this
 * component never string-searches headlines. Loads independently, so a news
 * failure cannot affect the chart or the analysis sections.
 */
export function CoinNewsSection({ coinId, coinName }: { coinId: string; coinName: string }) {
  const [page, setPage] = useState(1);
  const { data, loading, refreshing, error, retry } = useNewsList({ coinId, page, limit: PAGE_SIZE });

  return (
    <section
      aria-labelledby="coin-news-heading"
      className="mt-6 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="coin-news-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          Latest News
        </h2>
        <Link
          to={`/news?coin=${encodeURIComponent(coinId)}`}
          className="text-xs font-medium text-sky-700 hover:underline dark:text-sky-400"
        >
          See all {coinName} news
        </Link>
      </div>

      {data && <NewsFeedNotice status={data.status} showSentiment={false} />}
      {loading && <Loader label="Loading news..." />}
      {error && !data && <RetryError message={error.message} onRetry={retry} />}
      {error && data && <RetryError compact message={`Could not refresh news: ${error.message}`} onRetry={retry} />}

      {data && data.items.length === 0 && !error && (
        <EmptyState message={`No recent news is associated with ${coinName} yet.`} />
      )}

      {data && data.items.length > 0 && (
        <div aria-busy={refreshing}>
          <ul className={`space-y-2 ${refreshing ? "opacity-60" : ""}`}>
            {data.items.map((article) => (
              <li key={article.news_id}>
                <NewsCard article={article} compact showCoins={false} />
              </li>
            ))}
          </ul>
          <Pagination page={data.page} pages={data.pages} disabled={refreshing} label="coin news" onPageChange={setPage} />
        </div>
      )}
    </section>
  );
}
