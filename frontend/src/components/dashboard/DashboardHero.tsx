import { useId, useMemo } from "react";

import { FreshnessBadge } from "../common/FreshnessBadge";

interface DashboardHeroProps {
  name: string | undefined;
  /** 24H change of the TOTAL market cap (from the global market data); drives the trend badge. null = unknown. */
  change24h: number | null | undefined;
  lastUpdated: string | null | undefined;
}

function greeting(hour: number): string {
  if (hour < 5) return "Good night";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/** Decorative token + rising line; carries no data. */
function HeroArt() {
  const id = useId();
  return (
    <svg viewBox="0 0 420 220" className="h-full w-full" aria-hidden="true" focusable="false" preserveAspectRatio="xMaxYMid meet">
      <defs>
        <linearGradient id={`${id}-c`} x1="0.1" y1="0" x2="0.9" y2="1">
          <stop stopColor="#8fb2ff" />
          <stop offset="0.55" stopColor="#4f6dff" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
        <linearGradient id={`${id}-l`} x1="0" y1="0" x2="1" y2="0">
          <stop stopColor="#22d3ee" stopOpacity="0" />
          <stop offset="0.5" stopColor="#5b8cff" />
          <stop offset="1" stopColor="#a855f7" />
        </linearGradient>
        <radialGradient id={`${id}-h`}>
          <stop stopColor="#5b8cff" stopOpacity="0.5" />
          <stop offset="1" stopColor="#5b8cff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="300" cy="104" r="104" fill={`url(#${id}-h)`} className="animate-glow" />
      <path d="M0 190 60 170 110 182 170 140 220 156 280 108 330 124 420 70" fill="none" stroke={`url(#${id}-l)`} strokeWidth="2.5" strokeLinecap="round" />
      <g className="animate-float" style={{ transformBox: "fill-box", transformOrigin: "center" }}>
        <circle cx="300" cy="104" r="62" fill={`url(#${id}-c)`} />
        <circle cx="300" cy="104" r="62" fill="none" stroke="#fff" strokeOpacity="0.35" strokeWidth="1.5" />
        <circle cx="300" cy="104" r="50" fill="none" stroke="#fff" strokeOpacity="0.2" />
        <g fill="none" stroke="#fff" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M284 78h24c13 0 19 8 19 17s-6 15-18 15h-25z" />
          <path d="M284 110h30c14 0 21 8 21 17s-7 17-21 17h-30z" transform="translate(-4 -8) scale(1 .98)" />
          <path d="M284 78v62" />
          <path d="M294 66v12M308 66v12M294 140v12M308 140v12" strokeWidth="5" />
        </g>
      </g>
      <g stroke="#9ec1ff" strokeOpacity="0.3">
        <path d="M120 40 170 24 220 52M360 30 400 54" fill="none" />
      </g>
    </svg>
  );
}

/**
 * Personal welcome banner. Everything dynamic here is real: the name comes from the signed-in user (/auth/me),
 * the date from the device clock, and the trend badge from the global market data (shown only when present).
 * Crypto trades around the clock, so "Market Open" is a fixed, truthful label rather than a data value.
 */
export function DashboardHero({ name, change24h, lastUpdated }: DashboardHeroProps) {
  const now = useMemo(() => new Date(), []);
  const firstName = name?.trim().split(/\s+/)[0];
  const dateText = now.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  const hasTrend = typeof change24h === "number" && Number.isFinite(change24h);
  const trend = !hasTrend ? null : (change24h as number) > 0 ? "Bullish" : (change24h as number) < 0 ? "Bearish" : "Neutral";
  const trendTone = trend === "Bullish" ? "text-emerald-400" : trend === "Bearish" ? "text-rose-400" : "text-slate-400";

  return (
    <section
      aria-labelledby="dashboard-greeting"
      className="relative overflow-hidden rounded-card border border-slate-200 bg-white p-5 dark:border-brand-500/30 dark:shadow-glow dark:bg-gradient-to-br dark:from-brand-500/[0.18] dark:via-slate-900/60 dark:to-brand-violet/[0.22] sm:p-7"
    >
      <div aria-hidden="true" className="pointer-events-none absolute -left-16 -top-24 h-64 w-64 rounded-full bg-brand-500/20 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-0 hidden w-1/2 md:block">
        <HeroArt />
      </div>

      <div className="relative max-w-xl">
        <h1 id="dashboard-greeting" className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-3xl">
          {greeting(now.getHours())}
          {firstName ? `, ${firstName}` : ""} <span aria-hidden="true">👋</span>
        </h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300 sm:text-base">
          {name ? `Welcome back, ${name}. ` : ""}Here&apos;s what&apos;s happening in the crypto market today.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className="text-slate-500 dark:text-slate-400">{dateText}</span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-500 dark:text-emerald-400">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Market Open
          </span>
          {trend && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/60 px-3 py-1 dark:border-white/10 dark:bg-white/[0.05]">
              <span className="text-slate-500 dark:text-slate-400">24H trend</span>
              <span className={`font-semibold ${trendTone}`}>{trend}</span>
            </span>
          )}
          <FreshnessBadge lastUpdated={lastUpdated} />
        </div>
      </div>
    </section>
  );
}
