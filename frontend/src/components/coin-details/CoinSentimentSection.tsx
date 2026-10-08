import { useState } from "react";

import { useCoinSentiment } from "../../hooks/useCoinSentiment";
import type { CoinSentimentResponse, SentimentTimeframe, SentimentTrendDirection } from "../../types/news";
import { formatAbsoluteDateTime, formatRelativeTime } from "../../utils/formatters";
import { EmptyState } from "../common/EmptyState";
import { Loader } from "../common/Loader";
import { RetryError } from "../common/RetryError";
import { SentimentBadge } from "../news/SentimentBadge";

const PERIODS: { value: SentimentTimeframe; label: string; long: string }[] = [
  { value: "24h", label: "24 hours", long: "the last 24 hours" },
  { value: "7d", label: "7 days", long: "the last 7 days" },
];

const TREND_TEXT: Record<SentimentTrendDirection, string> = {
  improving: "Tone of coverage is more positive than in the previous period",
  declining: "Tone of coverage is more negative than in the previous period",
  stable: "Tone of coverage is about the same as in the previous period",
  insufficient_data: "Not enough articles in both periods to describe a trend",
};

function scoreText(score: number | null): string {
  return score === null ? "Not available" : `${score > 0 ? "+" : ""}${score.toFixed(2)}`;
}

/** Stacked distribution bar. Counts/percentages are printed beside it, so colour is never the only signal. */
function DistributionBar({ s }: { s: CoinSentimentResponse }) {
  const parts = [
    { key: "positive", pct: s.positive_percent ?? 0, color: "bg-emerald-500 dark:bg-emerald-400" },
    { key: "neutral", pct: s.neutral_percent ?? 0, color: "bg-slate-400 dark:bg-slate-500" },
    { key: "negative", pct: s.negative_percent ?? 0, color: "bg-red-500 dark:bg-red-400" },
  ];
  return (
    <div
      role="img"
      aria-label={`Sentiment distribution: ${s.positive_percent ?? 0}% positive, ${s.neutral_percent ?? 0}% neutral, ${s.negative_percent ?? 0}% negative`}
      className="flex h-3 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
    >
      {parts.map((part) => (
        <div key={part.key} className={part.color} style={{ width: `${part.pct}%` }} />
      ))}
    </div>
  );
}

/** Average tone per time bucket. Empty buckets are left blank (not drawn as zero). */
function TrendBars({ s }: { s: CoinSentimentResponse }) {
  const hasData = s.series.some((bucket) => bucket.average_score !== null);
  if (!hasData) return null;
  const H = 48;
  const mid = H / 2;
  return (
    <figure className="mt-3">
      <figcaption className="mb-1 text-xs text-slate-500 dark:text-slate-400">
        Average article tone over time (up = more positive, down = more negative)
      </figcaption>
      <svg viewBox={`0 0 ${s.series.length * 20} ${H}`} role="img" aria-label="Average sentiment score per time bucket" className="h-14 w-full">
        <line x1="0" x2={s.series.length * 20} y1={mid} y2={mid} className="stroke-slate-300 dark:stroke-slate-600" strokeWidth="0.5" />
        {s.series.map((bucket, i) => {
          if (bucket.average_score === null) return null;
          const h = Math.max(1, Math.abs(bucket.average_score) * (mid - 2));
          const positive = bucket.average_score >= 0;
          return (
            <rect
              key={bucket.bucket_start}
              x={i * 20 + 3}
              width={14}
              y={positive ? mid - h : mid}
              height={h}
              rx="1"
              className={positive ? "fill-emerald-500 dark:fill-emerald-400" : "fill-red-500 dark:fill-red-400"}
            >
              <title>{`${formatAbsoluteDateTime(bucket.bucket_start)}: ${bucket.article_count} article(s), average ${scoreText(bucket.average_score)}`}</title>
            </rect>
          );
        })}
      </svg>
    </figure>
  );
}

function SentimentBody({ s, periodLong }: { s: CoinSentimentResponse; periodLong: string }) {
  const unavailableModel = s.model_status === "unavailable" || s.model_status === "disabled";

  if (s.status === "insufficient_data") {
    return (
      <div className="space-y-2">
        <EmptyState
          message={
            s.total_articles === 0
              ? `Not enough analyzed news to describe sentiment for ${periodLong}.`
              : `Only ${s.total_articles} analyzed article${s.total_articles === 1 ? "" : "s"} in ${periodLong} — at least ${s.min_articles_required} are needed before a sentiment label is shown.`
          }
        />
        {unavailableModel && s.total_articles === 0 && (
          <p className="text-xs text-amber-800 dark:text-amber-300">
            Sentiment analysis is currently {s.model_status === "disabled" ? "disabled" : "unavailable"}, so new articles are not being analyzed.
          </p>
        )}
        {s.pending_article_count > 0 && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {s.pending_article_count} related article{s.pending_article_count === 1 ? " is" : "s are"} waiting to be analyzed.
          </p>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Overall tone of news</p>
          {s.sentiment_label && <SentimentBadge label={s.sentiment_label} score={s.average_score ?? undefined} />}
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Articles analyzed</dt>
            <dd className="font-semibold text-slate-900 dark:text-slate-100">{s.total_articles}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Average score</dt>
            <dd className="font-semibold text-slate-900 dark:text-slate-100" title="Mean of (P(positive) − P(negative)) per article, from −1 to +1">
              {scoreText(s.average_score)}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-3">
        <DistributionBar s={s} />
        <ul className="mt-2 grid grid-cols-3 gap-2 text-xs">
          <li className="text-emerald-800 dark:text-emerald-300">
            <span className="font-semibold">Positive {s.positive_percent?.toFixed(1)}%</span> ({s.positive_count})
          </li>
          <li className="text-slate-700 dark:text-slate-300">
            <span className="font-semibold">Neutral {s.neutral_percent?.toFixed(1)}%</span> ({s.neutral_count})
          </li>
          <li className="text-red-800 dark:text-red-300">
            <span className="font-semibold">Negative {s.negative_percent?.toFixed(1)}%</span> ({s.negative_count})
          </li>
        </ul>
      </div>

      <p className="mt-3 text-xs text-slate-600 dark:text-slate-300">
        <span className="font-medium">Trend: </span>
        {TREND_TEXT[s.trend.direction]}
        {s.trend.change !== null && ` (change in average score ${s.trend.change > 0 ? "+" : ""}${s.trend.change.toFixed(2)})`}.
      </p>
      <TrendBars s={s} />
      {s.pending_article_count > 0 && (
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          {s.pending_article_count} more related article{s.pending_article_count === 1 ? " is" : "s are"} not yet analyzed and not included.
        </p>
      )}
    </div>
  );
}

/**
 * News sentiment for the coin (Phase 12). Descriptive only: it summarizes the
 * tone of real, analyzed articles over a stated period. It is not a forecast,
 * score of the investment, or recommendation, and says so on screen.
 */
export function CoinSentimentSection({ coinId }: { coinId: string }) {
  const [timeframe, setTimeframe] = useState<SentimentTimeframe>("24h");
  const { sentiment, loading, error, retry } = useCoinSentiment(coinId, timeframe);
  const period = PERIODS.find((p) => p.value === timeframe)!;

  return (
    <section
      aria-labelledby="coin-sentiment-heading"
      className="mt-6 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="coin-sentiment-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            News Sentiment
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">Analysis period: {period.long}</p>
        </div>
        <div role="group" aria-label="Analysis period" className="flex rounded-lg border border-slate-200 p-0.5 dark:border-slate-700">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              type="button"
              aria-pressed={timeframe === p.value}
              onClick={() => setTimeframe(p.value)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
                timeframe === p.value
                  ? "bg-slate-900 text-white dark:bg-sky-600"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <Loader label="Loading sentiment..." />}
      {error && !sentiment && <RetryError message={error.message} onRetry={retry} />}
      {sentiment && <SentimentBody s={sentiment} periodLong={period.long} />}

      {sentiment && (
        <p className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
          {sentiment.disclaimer}{" "}
          <span title={formatAbsoluteDateTime(sentiment.calculated_at)}>Calculated {formatRelativeTime(sentiment.calculated_at)}.</span>
        </p>
      )}
    </section>
  );
}
