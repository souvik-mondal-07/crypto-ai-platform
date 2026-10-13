import { Link } from "react-router-dom";
import { ArrowRight, Bell, BarChart3, Search, Sparkles, Star, Wallet, type LucideIcon } from "lucide-react";

import { SectionHeading } from "../common/SectionHeading";

const TILE =
  "group flex min-h-[48px] items-center gap-2.5 rounded-xl border border-slate-200 bg-slate-50/60 px-3 py-2 text-left text-xs font-medium text-slate-800 transition-colors hover:border-brand-500/50 hover:bg-brand-500/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-brand-500/15 dark:bg-white/[0.03] dark:text-slate-100";

function Tile({ icon: Icon, label, tone }: { icon: LucideIcon; label: string; tone: string }) {
  return (
    <>
      <span aria-hidden="true" className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${tone}`}>
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <ArrowRight className="h-3.5 w-3.5 flex-shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
    </>
  );
}

interface QuickActionsProps {
  /** Where "AI Analysis" goes: the AI section of the largest coin's page when one is known, else Markets. */
  aiAnalysisPath: string;
  /** The command palette (Ctrl/Cmd+K) is only mounted for signed-in users; signed out, Search Coin opens Markets. */
  canSearch: boolean;
}

/** Shortcuts to existing destinations — every tile is a real link or opens the real command-palette search. */
export function QuickActions({ aiAnalysisPath, canSearch }: QuickActionsProps) {
  const openSearch = () => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }));
  return (
    <section aria-labelledby="quick-actions-heading" className="card card-pad h-full">
      <SectionHeading id="quick-actions-heading" title="Quick Actions" />
      <div className="grid grid-cols-1 gap-2.5 min-[480px]:grid-cols-2 3xl:grid-cols-3">
        <Link to="/markets" className={TILE}>
          <Tile icon={BarChart3} label="Explore Markets" tone="bg-brand-500/20 text-brand-400" />
        </Link>
        {canSearch ? (
          <button type="button" onClick={openSearch} className={TILE}>
            <Tile icon={Search} label="Search Coin" tone="bg-brand-violet/20 text-violet-300" />
          </button>
        ) : (
          <Link to="/markets" className={TILE}>
            <Tile icon={Search} label="Search Coin" tone="bg-brand-violet/20 text-violet-300" />
          </Link>
        )}
        <Link to={aiAnalysisPath} className={TILE}>
          <Tile icon={Sparkles} label="AI Analysis" tone="bg-fuchsia-500/20 text-fuchsia-300" />
        </Link>
        <Link to="/watchlist" className={TILE}>
          <Tile icon={Star} label="Watchlist" tone="bg-amber-500/20 text-amber-300" />
        </Link>
        <Link to="/portfolio" className={TILE}>
          <Tile icon={Wallet} label="Portfolio" tone="bg-cyan-500/20 text-cyan-300" />
        </Link>
        <Link to="/alerts" className={TILE}>
          <Tile icon={Bell} label="Alerts" tone="bg-rose-500/20 text-rose-300" />
        </Link>
      </div>
    </section>
  );
}
