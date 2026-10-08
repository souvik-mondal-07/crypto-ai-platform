import { Link } from "react-router-dom";
import { Activity, BarChart3, Clock, Coins, Flame, Layers, type LucideIcon } from "lucide-react";

import { SectionHeading } from "../common/SectionHeading";
import { useUserListsStore } from "../../store/userListsStore";

interface Action {
  label: string;
  hint: string;
  to: string;
  icon: LucideIcon;
}

/**
 * Quick Discovery: shortcuts into the Markets explorer with a filter already
 * applied. These are navigation links only — they carry no data of their own,
 * so there is nothing here that could be fabricated. Every target is a tab or
 * preset defined in utils/marketFilters.ts.
 */
const ACTIONS: Action[] = [
  { label: "Trending Coins", hint: "What's gaining attention", to: "/markets?tab=trending", icon: Flame },
  { label: "Highest Volume", hint: "Most traded in 24H", to: "/markets?tab=volume", icon: BarChart3 },
  { label: "Highest Volatility", hint: "Widest 24H price range", to: "/markets?tab=volatility", icon: Activity },
  { label: "Large Cap", hint: "Above $10B market cap", to: "/markets?cap=gt10b", icon: Layers },
  { label: "Small Cap", hint: "Below $1B market cap", to: "/markets?cap=lt1b", icon: Coins },
];

export function QuickDiscovery() {
  const hasRecent = useUserListsStore((state) => state.recent.length > 0);

  return (
    <section aria-labelledby="quick-discovery-heading">
      <SectionHeading id="quick-discovery-heading" title="Quick Discovery" description="Jump into the Markets explorer, pre-filtered" />
      <ul className="flex flex-wrap gap-2">
        {ACTIONS.map(({ label, hint, to, icon: Icon }) => (
          <li key={label}>
            <Link
              to={to}
              title={hint}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:border-sky-300 hover:bg-sky-50 hover:text-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-sky-700 dark:hover:bg-sky-950/40 dark:hover:text-sky-300"
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </Link>
          </li>
        ))}
        {hasRecent && (
          <li>
            <a
              href="#recently-viewed"
              title="Coins you opened recently"
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:border-sky-300 hover:bg-sky-50 hover:text-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-sky-700 dark:hover:bg-sky-950/40 dark:hover:text-sky-300"
            >
              <Clock className="h-4 w-4" aria-hidden="true" />
              Recently Viewed
            </a>
          </li>
        )}
      </ul>
    </section>
  );
}
