import { useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";

import type { NewsArticle } from "../../types/news";
import { formatAbsoluteDateTime, formatRelativeTime } from "../../utils/formatters";
import { SentimentBadge } from "./SentimentBadge";

interface NewsCardProps {
  article: NewsArticle;
  /** Compact rows (no image/summary) for the Coin Details and Dashboard lists. */
  compact?: boolean;
  /** Related-coin chips; hidden on a coin's own page where they'd be redundant. */
  showCoins?: boolean;
}

const MAX_COIN_CHIPS = 4;

function CoinChips({ article }: { article: NewsArticle }) {
  const coins = article.related_coins;
  if (coins.length === 0) return null;
  return (
    <ul aria-label="Related coins" className="flex flex-wrap items-center gap-1">
      {coins.slice(0, MAX_COIN_CHIPS).map((coin) => (
        <li key={coin.coin_id}>
          <Link
            to={`/coins/${coin.coin_id}`}
            title={coin.name ?? coin.symbol}
            className="rounded-md bg-sky-50 px-1.5 py-0.5 text-xs font-medium text-sky-800 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:bg-sky-950/50 dark:text-sky-300"
          >
            {coin.symbol}
          </Link>
        </li>
      ))}
      {coins.length > MAX_COIN_CHIPS && (
        <li className="text-xs text-slate-500 dark:text-slate-400">+{coins.length - MAX_COIN_CHIPS}</li>
      )}
    </ul>
  );
}

/**
 * One real article. The headline links to the ORIGINAL publisher URL returned
 * by the provider (opened in a new tab) — the app never rewrites or invents a link.
 */
export function NewsCard({ article, compact = false, showCoins = true }: NewsCardProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = !compact && article.image_url && !imageFailed;

  return (
    <article className="flex gap-3 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      {showImage && (
        <img
          src={article.image_url as string}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setImageFailed(true)}
          className="hidden h-24 w-36 flex-shrink-0 rounded-lg bg-slate-100 object-cover dark:bg-slate-800 sm:block"
        />
      )}
      <div className="min-w-0 flex-1">
        <h3 className="text-sm font-semibold leading-snug text-slate-900 dark:text-slate-100">
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

        {!compact && article.description && (
          <p className="mt-1 line-clamp-2 text-sm text-slate-600 dark:text-slate-300">{article.description}</p>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
          <span className="font-medium text-slate-700 dark:text-slate-200">{article.source}</span>
          <time dateTime={article.published_at} title={formatAbsoluteDateTime(article.published_at)}>
            {formatRelativeTime(article.published_at)}
          </time>
          {article.sentiment && <SentimentBadge label={article.sentiment.label} score={article.sentiment.score} />}
          {showCoins && <CoinChips article={article} />}
        </div>
      </div>
    </article>
  );
}
