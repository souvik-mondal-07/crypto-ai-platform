import { Link } from "react-router-dom";

import { CoinLogo } from "../market/CoinLogo";
import { SectionHeading } from "../common/SectionHeading";
import { useUserListsStore } from "../../store/userListsStore";
import { formatRelativeTime } from "../../utils/formatters";

/**
 * Recently viewed coins. Populated only by coins this user actually opened
 * (recorded on the Coin Details page) and stored in this browser — the
 * backend has no view-history API yet, so there is no cross-device sync, and
 * the empty state says what fills the list instead of showing sample coins.
 */
export function RecentlyViewed() {
  const recent = useUserListsStore((state) => state.recent);
  const clearRecent = useUserListsStore((state) => state.clearRecent);

  return (
    <section id="recently-viewed" aria-labelledby="recently-viewed-heading" className="scroll-mt-24">
      <SectionHeading
        id="recently-viewed-heading"
        title="Recently Viewed"
        description="Saved on this device"
        actions={
          recent.length > 0 ? (
            <button type="button" onClick={clearRecent} className="text-xs font-medium text-slate-500 hover:underline dark:text-slate-400">
              Clear
            </button>
          ) : undefined
        }
      />

      {recent.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          Coins you open will appear here.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {recent.map((coin) => (
            <li key={coin.coin_id}>
              <Link
                to={`/coins/${coin.coin_id}`}
                className="flex items-center gap-3 rounded-md px-1 py-2 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:hover:bg-slate-800/60"
              >
                <CoinLogo src={coin.logo_url} alt="" size={24} />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800 dark:text-slate-100">{coin.name}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">{coin.symbol.toUpperCase()}</span>
                <span className="hidden text-xs text-slate-400 sm:inline">{formatRelativeTime(coin.viewed_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
