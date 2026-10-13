import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ExternalLink, Newspaper } from "lucide-react";

import { useNewsList } from "../../hooks/useNewsList";
import { formatAbsoluteDateTime, formatRelativeTime } from "../../utils/formatters";
import type { NewsArticle } from "../../types/news";
import { EmptyState } from "../common/EmptyState";
import { Loader } from "../common/Loader";
import { RetryError } from "../common/RetryError";
import { SectionHeading } from "../common/SectionHeading";
import { SentimentBadge } from "../news/SentimentBadge";

const QUERY = { page: 1, limit: 4 };

/** One article as a horizontal card: thumbnail (or a neutral placeholder if there is none / it fails), headline, source, time. */
function NewsTile({ article }: { article: NewsArticle }) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = !!article.image_url && !imageFailed;
  return (
    <article className="flex h-full gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-2.5 transition-colors hover:border-brand-500/40 dark:border-brand-500/15 dark:bg-white/[0.03]">
      {showImage ? (
        <img
          src={article.image_url as string}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setImageFailed(true)}
          className="h-20 w-20 flex-shrink-0 rounded-lg bg-slate-100 object-cover dark:bg-slate-800"
        />
      ) : (
        <div aria-hidden="true" className="flex h-20 w-20 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500/25 to-brand-violet/25 text-brand-400">
          <Newspaper className="h-6 w-6" />
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <h3 className="line-clamp-3 text-xs font-semibold leading-snug text-slate-900 dark:text-slate-100">
          <a
            href={article.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-sky-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:hover:text-sky-300"
          >
            {article.title}
            <ExternalLink className="ml-1 inline h-3 w-3 align-baseline text-slate-400" aria-hidden="true" />
            <span className="sr-only"> (opens the original article in a new tab)</span>
          </a>
        </h3>
        <div className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 pt-1.5 text-[11px] text-slate-500 dark:text-slate-400">
          <span className="font-medium text-slate-700 dark:text-slate-200">{article.source}</span>
          <time dateTime={article.published_at} title={formatAbsoluteDateTime(article.published_at)}>
            {formatRelativeTime(article.published_at)}
          </time>
          {article.sentiment && <SentimentBadge label={article.sentiment.label} score={article.sentiment.score} />}
        </div>
      </div>
    </article>
  );
}

/** Dashboard "Latest News": the newest real articles as a horizontal strip, with a link to the full News page. */
export function LatestNews() {
  const { data, loading, error, retry } = useNewsList(QUERY);
  return (
    <section aria-labelledby="market-news-heading" className="card card-pad h-full">
      <SectionHeading
        id="market-news-heading"
        title="Latest News"
        actions={
          <Link to="/news" aria-label="View all news" className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:underline dark:text-sky-400">
            View All <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        }
      />
      {loading && <Loader label="Loading news..." />}
      {error && !data && <RetryError compact message={error.message} onRetry={retry} />}
      {data && data.items.length === 0 && !error && <EmptyState message="No news articles are stored yet." />}
      {data && data.items.length > 0 && (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 3xl:grid-cols-4">
          {data.items.map((article) => (
            <li key={article.news_id} className="min-w-0">
              <NewsTile article={article} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
