import { CoinLogo } from "../market/CoinLogo";
import { ChangeBadge } from "../common/ChangeBadge";
import { formatUsd } from "../../utils/formatters";
import type { CoinSearchResult } from "../../types/coin";

interface SearchResultRowProps {
  coin: CoinSearchResult;
  active: boolean;
  id: string;
  onSelect: () => void;
  onHover: () => void;
}

/** One suggestion: logo, name, symbol, rank and price when the backend has them (else "N/A"/omitted). */
export function SearchResultRow({ coin, active, id, onSelect, onHover }: SearchResultRowProps) {
  return (
    <li
      id={id}
      role="option"
      aria-selected={active}
      onMouseEnter={onHover}
      // mousedown (not click) so the input's blur doesn't close the list before the selection registers.
      onMouseDown={(event) => {
        event.preventDefault();
        onSelect();
      }}
      className={`flex cursor-pointer items-center gap-3 px-3 py-2 ${active ? "bg-sky-50 dark:bg-slate-800" : ""}`}
    >
      <CoinLogo src={coin.logo_url} alt="" size={24} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-100">
          {coin.name} <span className="font-normal text-slate-500 dark:text-slate-400">{coin.symbol.toUpperCase()}</span>
        </span>
        {coin.market_cap_rank !== null && (
          <span className="block text-xs text-slate-500 dark:text-slate-400">Rank #{coin.market_cap_rank}</span>
        )}
      </span>
      <span className="flex-shrink-0 text-right">
        <span className="block text-sm tabular-nums text-slate-700 dark:text-slate-200">{formatUsd(coin.price_usd)}</span>
        <ChangeBadge value={coin.percent_change_24h} className="text-xs" />
      </span>
    </li>
  );
}
