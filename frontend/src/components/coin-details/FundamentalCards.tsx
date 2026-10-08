import { useState, type ReactNode } from "react";

import {
  changeColorClass,
  formatAbsoluteDateTime,
  formatCompactNumber,
  formatCompactUsd,
  formatDecimal,
  formatPercent,
  formatPlainPercent,
  formatRatio,
  formatSupply,
  formatUsd,
} from "../../utils/formatters";
import { htmlToPlainText, linkLabel, safeHttpUrl, socialProfileUrl, truncateMiddle } from "../../utils/providerText";
import type {
  CalculatedMetric,
  CalculatedMetrics,
  EcosystemData,
  FundamentalScore,
  MarketOverview,
  ProjectInfo,
  SummaryItem,
  SupplyData,
  SupplyType,
  ValuationData,
} from "../../types/fundamentals";

export const NOT_AVAILABLE_LABEL = "Not available";

const CARD = "rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900";
const BADGE_BASE = "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide";

export function ProviderBadge() {
  return (
    <span className={`${BADGE_BASE} bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300`}>
      Provider-reported
    </span>
  );
}

export function CalculatedBadge() {
  return (
    <span className={`${BADGE_BASE} bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300`}>
      Calculated
    </span>
  );
}

export function FundamentalCard({ title, badge, children }: { title: string; badge?: ReactNode; children: ReactNode }) {
  return (
    <div className={CARD}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
        {badge}
      </div>
      {children}
    </div>
  );
}

/** A value, or a muted "Not available" — never a blank, NaN or invented figure. */
function Value({ text, className = "" }: { text: string | null; className?: string }) {
  if (text === null) {
    return <span className="text-slate-400 dark:text-slate-500">{NOT_AVAILABLE_LABEL}</span>;
  }
  return <span className={`font-semibold text-slate-900 dark:text-slate-100 ${className}`}>{text}</span>;
}

function Row({ label, text, className, hint }: { label: string; text: string | null; className?: string; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 text-sm" title={hint}>
      <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="text-right">
        <Value text={text} className={className} />
      </dd>
    </div>
  );
}

/** Formats with the shared formatter, mapping its "N/A" sentinel for null to null so `Value` renders "Not available". */
const orNull = <T,>(value: T | null | undefined, format: (v: T) => string): string | null =>
  value === null || value === undefined ? null : format(value);

function ExternalLink({ url, label }: { url: string; label?: string }) {
  const safe = safeHttpUrl(url);
  if (!safe) return null;
  return (
    <a
      href={safe}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className="break-all text-sky-600 hover:underline dark:text-sky-400"
    >
      {label ?? linkLabel(safe)}
    </a>
  );
}

function LinkList({ label, urls }: { label: string; urls: string[] }) {
  const safe = urls.filter((u) => safeHttpUrl(u) !== null);
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 text-sm">
      <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="flex flex-wrap justify-end gap-x-3 gap-y-1 text-right">
        {safe.length === 0 ? (
          <Value text={null} />
        ) : (
          safe.slice(0, 4).map((url) => <ExternalLink key={url} url={url} />)
        )}
      </dd>
    </div>
  );
}

// ---------------------------------------------------------------------------

export function MarketOverviewCard({ market }: { market: MarketOverview | null }) {
  return (
    <FundamentalCard title="Market Overview" badge={<ProviderBadge />}>
      {market === null ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">{NOT_AVAILABLE_LABEL}</p>
      ) : (
        <dl className="divide-y divide-slate-100 dark:divide-slate-800">
          <Row label="Market cap" text={orNull(market.market_cap_usd, formatCompactUsd)} />
          <Row label="Market-cap rank" text={orNull(market.market_cap_rank, (r) => `#${r}`)} />
          <Row label="24h volume" text={orNull(market.volume_24h_usd, formatCompactUsd)} />
          <Row label="Fully diluted valuation" text={orNull(market.fully_diluted_valuation_usd, formatCompactUsd)} />
        </dl>
      )}
    </FundamentalCard>
  );
}

const SUPPLY_TYPE_LABEL: Record<SupplyType, string> = {
  capped: "Capped supply",
  unlimited: "Unlimited supply (per provider)",
  not_reported: "Maximum supply not reported",
};

export function SupplyCard({ supply, metrics }: { supply: SupplyData | null; metrics: CalculatedMetrics }) {
  return (
    <FundamentalCard title="Supply" badge={<ProviderBadge />}>
      {supply === null ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">{NOT_AVAILABLE_LABEL}</p>
      ) : (
        <>
          <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">{SUPPLY_TYPE_LABEL[supply.supply_type]}</p>
          <dl className="divide-y divide-slate-100 dark:divide-slate-800">
            <Row label="Circulating supply" text={orNull(supply.circulating_supply, formatSupply)} />
            <Row label="Total supply" text={orNull(supply.total_supply, formatSupply)} />
            <Row
              label="Maximum supply"
              text={
                supply.max_supply !== null
                  ? formatSupply(supply.max_supply)
                  : supply.supply_type === "unlimited"
                    ? "Unlimited"
                    : null
              }
            />
          </dl>
          <div className="mt-3 flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">Derived from the figures above</p>
            <CalculatedBadge />
          </div>
          <dl className="divide-y divide-slate-100 dark:divide-slate-800">
            <Row
              label="Circulating / maximum"
              text={orNull(metrics.circulating_to_max_supply_percent.value, formatPlainPercent)}
              hint={metrics.circulating_to_max_supply_percent.unavailable_reason ?? metrics.circulating_to_max_supply_percent.formula}
            />
            <Row
              label="Remaining to maximum"
              text={orNull(metrics.remaining_supply_to_max.value, formatSupply)}
              hint={metrics.remaining_supply_to_max.unavailable_reason ?? metrics.remaining_supply_to_max.formula}
            />
            <Row
              label="Circulating / total"
              text={orNull(metrics.circulating_to_total_supply_percent.value, formatPlainPercent)}
              hint={metrics.circulating_to_total_supply_percent.unavailable_reason ?? metrics.circulating_to_total_supply_percent.formula}
            />
          </dl>
          {supply.notes.map((note) => (
            <p key={note} className="mt-2 text-xs text-slate-400">
              {note}
            </p>
          ))}
        </>
      )}
    </FundamentalCard>
  );
}

export function ValuationCard({ valuation }: { valuation: ValuationData | null }) {
  return (
    <FundamentalCard title="Valuation" badge={<ProviderBadge />}>
      {valuation === null ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">{NOT_AVAILABLE_LABEL}</p>
      ) : (
        <>
          <dl className="divide-y divide-slate-100 dark:divide-slate-800">
            <Row label="All-time high" text={orNull(valuation.ath_usd, formatUsd)} />
            <Row label="ATH date" text={orNull(valuation.ath_date, (d) => formatAbsoluteDateTime(d))} />
            <Row
              label="From ATH (provider)"
              text={orNull(valuation.ath_change_percentage, formatPercent)}
              className={changeColorClass(valuation.ath_change_percentage)}
              hint="Reported by the provider as of its last sync"
            />
            <Row label="All-time low" text={orNull(valuation.atl_usd, formatUsd)} />
            <Row label="ATL date" text={orNull(valuation.atl_date, (d) => formatAbsoluteDateTime(d))} />
            <Row
              label="From ATL (provider)"
              text={orNull(valuation.atl_change_percentage, formatPercent)}
              className={changeColorClass(valuation.atl_change_percentage)}
              hint="Reported by the provider as of its last sync"
            />
          </dl>
          <p className="mt-2 text-xs text-slate-400">
            Current price and price performance are shown at the top of this page.
          </p>
        </>
      )}
    </FundamentalCard>
  );
}

function metricText(metric: CalculatedMetric, formatter: (v: number) => string): string | null {
  return metric.value === null ? null : formatter(metric.value);
}

function MetricRow({ label, metric, formatter, colored }: { label: string; metric: CalculatedMetric; formatter: (v: number) => string; colored?: boolean }) {
  return (
    <div className="py-1.5">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <dt className="text-slate-500 dark:text-slate-400" title={`Formula: ${metric.formula}`}>
          {label}
        </dt>
        <dd className="text-right">
          <Value text={metricText(metric, formatter)} className={colored ? changeColorClass(metric.value) : ""} />
        </dd>
      </div>
      {metric.value === null && metric.unavailable_reason && (
        <p className="text-right text-xs text-slate-400 dark:text-slate-500">{metric.unavailable_reason}</p>
      )}
    </div>
  );
}

export function CalculatedMetricsCard({ metrics }: { metrics: CalculatedMetrics }) {
  return (
    <FundamentalCard title="Calculated Metrics" badge={<CalculatedBadge />}>
      <p className="mb-1 text-xs text-slate-400">
        Derived by this platform from the provider-reported figures; hover a label for its formula.
      </p>
      <dl className="divide-y divide-slate-100 dark:divide-slate-800">
        <MetricRow
          label="Volume / market cap"
          metric={metrics.volume_to_market_cap}
          formatter={(v) => `${formatRatio(v)} (${formatPlainPercent(v * 100)})`}
        />
        <MetricRow
          label="Market cap / FDV"
          metric={metrics.market_cap_to_fdv}
          formatter={(v) => `${formatRatio(v)} (${formatPlainPercent(v * 100)})`}
        />
        <MetricRow label="Circulating / max supply" metric={metrics.circulating_to_max_supply_percent} formatter={(v) => formatPlainPercent(v)} />
        <MetricRow label="Distance from ATH" metric={metrics.distance_from_ath_percent} formatter={formatPercent} colored />
        <MetricRow label="Distance from ATL" metric={metrics.distance_from_atl_percent} formatter={formatPercent} colored />
      </dl>
    </FundamentalCard>
  );
}

// ---------------------------------------------------------------------------

export function ProjectInfoCard({ project }: { project: ProjectInfo | null }) {
  const [showFull, setShowFull] = useState(false);

  if (project === null) {
    return (
      <FundamentalCard title="Project Information" badge={<ProviderBadge />}>
        <p className="text-sm text-slate-400 dark:text-slate-500">{NOT_AVAILABLE_LABEL}</p>
      </FundamentalCard>
    );
  }

  const description = htmlToPlainText(project.description);
  const isLong = description.length > 320;
  const contracts = Object.entries(project.contract_addresses);

  return (
    <FundamentalCard title="Project Information" badge={<ProviderBadge />}>
      {description ? (
        <div className="mb-2">
          <p className="whitespace-pre-line text-sm text-slate-700 dark:text-slate-300">
            {isLong && !showFull ? `${description.slice(0, 320).trimEnd()}…` : description}
          </p>
          {isLong && (
            <button
              type="button"
              onClick={() => setShowFull((v) => !v)}
              className="mt-1 text-xs font-medium text-sky-600 hover:underline dark:text-sky-400"
            >
              {showFull ? "Show less" : "Read more"}
            </button>
          )}
        </div>
      ) : (
        <p className="mb-2 text-sm text-slate-400 dark:text-slate-500">Description: {NOT_AVAILABLE_LABEL}</p>
      )}

      {project.categories.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-1.5" aria-label="Categories">
          {project.categories.slice(0, 8).map((category) => (
            <li
              key={category}
              className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300"
            >
              {category}
            </li>
          ))}
        </ul>
      )}

      <dl className="divide-y divide-slate-100 dark:divide-slate-800">
        <LinkList label="Website" urls={project.homepage_urls} />
        <div className="flex items-baseline justify-between gap-3 py-1.5 text-sm">
          <dt className="text-slate-500 dark:text-slate-400">Whitepaper</dt>
          <dd className="text-right">
            {project.whitepaper_url && safeHttpUrl(project.whitepaper_url) ? (
              <ExternalLink url={project.whitepaper_url} />
            ) : (
              <Value text={null} />
            )}
          </dd>
        </div>
        <LinkList label="Block explorers" urls={project.blockchain_explorer_urls} />
        <Row label="Launch (genesis) date" text={project.genesis_date} />
        <Row label="Blockchain / platform" text={project.asset_platform_id} />
        <Row label="Hashing algorithm" text={project.hashing_algorithm} />
        <Row label="Block time" text={orNull(project.block_time_in_minutes, (m) => `${formatDecimal(m)} min`)} />
      </dl>

      {contracts.length > 0 && (
        <div className="mt-2">
          <p className="mb-1 text-xs font-semibold text-slate-600 dark:text-slate-300">Contract addresses</p>
          <ul className="space-y-1">
            {contracts.slice(0, 6).map(([platform, address]) => (
              <li key={platform} className="flex items-baseline justify-between gap-3 text-xs">
                <span className="text-slate-500 dark:text-slate-400">{platform}</span>
                <code className="text-slate-800 dark:text-slate-200" title={address}>
                  {truncateMiddle(address)}
                </code>
              </li>
            ))}
          </ul>
        </div>
      )}
    </FundamentalCard>
  );
}

export function EcosystemCard({ ecosystem }: { ecosystem: EcosystemData | null }) {
  if (ecosystem === null) {
    return (
      <FundamentalCard title="Development & Ecosystem" badge={<ProviderBadge />}>
        <p className="text-sm text-slate-400 dark:text-slate-500">{NOT_AVAILABLE_LABEL}</p>
      </FundamentalCard>
    );
  }

  const { development: dev, community } = ecosystem;
  const xUrl = socialProfileUrl("https://x.com/", community.twitter_screen_name);
  const telegramUrl = socialProfileUrl("https://t.me/", community.telegram_channel_identifier);
  const repos = dev.repositories.filter((r) => safeHttpUrl(r) !== null);

  return (
    <FundamentalCard title="Development & Ecosystem" badge={<ProviderBadge />}>
      <p className="mb-1 text-xs font-semibold text-slate-600 dark:text-slate-300">Development</p>
      {dev.available ? (
        <dl className="divide-y divide-slate-100 dark:divide-slate-800">
          <Row label="Commits (last 4 weeks)" text={orNull(dev.commit_count_4_weeks, formatSupply)} />
          <Row label="PR contributors" text={orNull(dev.pull_request_contributors, formatSupply)} />
          <Row label="Pull requests merged" text={orNull(dev.pull_requests_merged, formatCompactNumber)} />
          <Row label="Stars" text={orNull(dev.stars, formatCompactNumber)} />
          <Row label="Forks" text={orNull(dev.forks, formatCompactNumber)} />
          <Row
            label="Issues"
            text={
              dev.total_issues === null
                ? null
                : dev.closed_issues === null
                  ? `${formatCompactNumber(dev.total_issues)} total`
                  : `${formatCompactNumber(dev.closed_issues)} closed of ${formatCompactNumber(dev.total_issues)}`
            }
          />
        </dl>
      ) : (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          {repos.length > 0
            ? "The provider reports no activity figures for the linked repositories."
            : "No development data or code repository reported by the provider."}
        </p>
      )}
      {repos.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm">
          {repos.slice(0, 3).map((url) => (
            <ExternalLink key={url} url={url} />
          ))}
        </div>
      )}

      <p className="mb-1 mt-3 text-xs font-semibold text-slate-600 dark:text-slate-300">Community</p>
      <dl className="divide-y divide-slate-100 dark:divide-slate-800">
        <LinkList label="Forum" urls={community.official_forum_urls} />
        <LinkList label="Chat" urls={community.chat_urls} />
        <LinkList label="Announcements" urls={community.announcement_urls} />
        <div className="flex items-baseline justify-between gap-3 py-1.5 text-sm">
          <dt className="text-slate-500 dark:text-slate-400">Social</dt>
          <dd className="flex flex-wrap justify-end gap-x-3 text-right">
            {xUrl && <ExternalLink url={xUrl} label="X / Twitter" />}
            {community.subreddit_url && safeHttpUrl(community.subreddit_url) && <ExternalLink url={community.subreddit_url} label="Reddit" />}
            {telegramUrl && <ExternalLink url={telegramUrl} label="Telegram" />}
            {!xUrl && !telegramUrl && !(community.subreddit_url && safeHttpUrl(community.subreddit_url)) && <Value text={null} />}
          </dd>
        </div>
        {/* The provider reports 0 for audiences it doesn't track, so 0 is shown as not available rather than as a measured zero. */}
        <Row label="Reddit subscribers" text={orNull(community.reddit_subscribers && community.reddit_subscribers > 0 ? community.reddit_subscribers : null, formatCompactNumber)} />
        <Row label="Telegram members" text={orNull(community.telegram_channel_user_count && community.telegram_channel_user_count > 0 ? community.telegram_channel_user_count : null, formatCompactNumber)} />
      </dl>
    </FundamentalCard>
  );
}

// ---------------------------------------------------------------------------

export function ScoreCard({ score }: { score: FundamentalScore }) {
  const scored = score.status === "scored" && score.score !== null;
  return (
    <FundamentalCard title="Fundamental Score" badge={<CalculatedBadge />}>
      {scored ? (
        <div className="flex items-end gap-2">
          <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">{formatDecimal(score.score, 1)}</p>
          <p className="pb-1 text-sm text-slate-400">/ 100</p>
        </div>
      ) : (
        <div>
          <p className="text-lg font-semibold text-slate-700 dark:text-slate-200">{score.message ?? "Not enough data"}</p>
          <p className="mt-1 text-xs text-slate-400">
            A score needs at least {score.min_coverage_percent}% of the scoring weight backed by real data; only{" "}
            {score.coverage_percent}% is currently available.
          </p>
        </div>
      )}

      {scored && (
        <div className="mt-2">
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
            role="progressbar"
            aria-label="Fundamental score"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={score.score ?? 0}
          >
            <div className="h-full rounded-full bg-sky-500" style={{ width: `${Math.max(0, Math.min(100, score.score ?? 0))}%` }} />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Based on {score.coverage_percent}% of the scoring weight (the rest lacks provider data).
          </p>
        </div>
      )}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">Fundamental score components</caption>
          <thead>
            <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <th scope="col" className="py-1 pr-2 font-medium">Component</th>
              <th scope="col" className="py-1 pr-2 text-right font-medium">Weight</th>
              <th scope="col" className="py-1 pr-2 text-right font-medium">Sub-score</th>
              <th scope="col" className="py-1 font-medium">Input</th>
            </tr>
          </thead>
          <tbody>
            {score.components.map((c) => (
              <tr key={c.key} className="border-b border-slate-100 align-top last:border-0 dark:border-slate-800">
                <td className="py-1.5 pr-2 text-slate-700 dark:text-slate-200">{c.label}</td>
                <td className="py-1.5 pr-2 text-right text-slate-600 dark:text-slate-300">{c.weight}</td>
                <td className="py-1.5 pr-2 text-right font-semibold text-slate-900 dark:text-slate-100">
                  {c.available && c.subscore !== null ? formatDecimal(c.subscore, 1) : <span className="font-normal text-slate-400">{NOT_AVAILABLE_LABEL}</span>}
                </td>
                <td className="py-1.5 text-slate-500 dark:text-slate-400">{c.input_description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        <summary className="cursor-pointer font-medium text-sky-600 dark:text-sky-400">How this score is calculated</summary>
        <p className="mt-2">
          Weighted average of the sub-scores that real data supports (method v{score.method_version}). Missing inputs lower
          coverage; they are never guessed or scored as zero. Price movement is deliberately excluded.
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-4">
          {score.components.map((c) => (
            <li key={c.key}>
              <span className="font-medium text-slate-600 dark:text-slate-300">{c.label} ({c.weight}):</span> {c.rule}
            </li>
          ))}
        </ul>
        <p className="mt-2">{score.disclaimer}</p>
      </details>
    </FundamentalCard>
  );
}

const SUMMARY_CATEGORY_LABEL: Record<SummaryItem["category"], string> = {
  market_position: "Market position",
  liquidity: "Trading volume",
  supply: "Supply",
  valuation: "Distance from extremes",
  project: "Project",
  development: "Development",
};

export function SummaryCard({ summary }: { summary: SummaryItem[] }) {
  return (
    <FundamentalCard title="Fundamental Summary">
      {summary.length === 0 ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">{NOT_AVAILABLE_LABEL}</p>
      ) : (
        <ul className="space-y-1.5">
          {summary.map((item) => (
            <li key={`${item.category}-${item.text}`} className="text-sm text-slate-700 dark:text-slate-300">
              <span className="mr-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                {SUMMARY_CATEGORY_LABEL[item.category]}
              </span>
              {item.text}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-slate-400">
        Factual statements generated from the figures above. For informational purposes only — not investment advice.
      </p>
    </FundamentalCard>
  );
}
