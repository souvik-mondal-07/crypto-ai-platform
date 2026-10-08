import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";

import { fetchMarketCoins } from "../../services/api/market.api";
import { ChangeBadge } from "../common/ChangeBadge";
import { RetryError } from "../common/RetryError";
import { CoinLogo } from "../market/CoinLogo";
import { toErrorMessage } from "../../utils/apiErrors";
import { dedupe } from "../../utils/dedupe";
import { formatCompactUsd, formatSupply, formatUsd } from "../../utils/formatters";
import type { MarketCoin } from "../../types/market";

interface ComparePanelProps {
  coinIds: string[];
  onRemove: (coinId: string) => void;
  onClear: () => void;
  onClose: () => void;
}

interface Metric {
  label: string;
  render: (coin: MarketCoin) => React.ReactNode;
}

const METRICS: Metric[] = [
  { label: "Rank", render: (c) => (c.market_cap_rank !== null ? `#${c.market_cap_rank}` : "N/A") },
  { label: "Price", render: (c) => formatUsd(c.price_usd) },
  { label: "24H Change", render: (c) => <ChangeBadge value={c.percent_change_24h} /> },
  { label: "7D Change", render: (c) => <ChangeBadge value={c.percent_change_7d ?? null} /> },
  { label: "Market Cap", render: (c) => formatCompactUsd(c.market_cap_usd) },
  { label: "24H Volume", render: (c) => formatCompactUsd(c.volume_24h_usd) },
  { label: "FDV", render: (c) => formatCompactUsd(c.fully_diluted_valuation_usd) },
  { label: "Circulating Supply", render: (c) => formatSupply(c.circulating_supply) },
  { label: "Max Supply", render: (c) => formatSupply(c.max_supply ?? null) },
  { label: "ATH", render: (c) => formatUsd(c.ath_usd) },
  { label: "ATL", render: (c) => formatUsd(c.atl_usd) },
];

/**
 * Side-by-side comparison of the coins ticked in the Markets table. Metrics
 * come from the SAME real endpoint as the table (`/market/coins?coin_ids=`),
 * so there is no separate comparison backend to drift; unavailable values show
 * "N/A". Needs at least two coins.
 */
export function ComparePanel({ coinIds, onRemove, onClear, onClose }: ComparePanelProps) {
  const [coins, setCoins] = useState<MarketCoin[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = coinIds.join(",");

  useEffect(() => {
    if (coinIds.length < 2) {
      setCoins([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    dedupe(`compare:${key}`, () => fetchMarketCoins({ page: 1, limit: coinIds.length, coinIds }))
      .then((response) => {
        if (cancelled) return;
        // Keep the user's selection order.
        const byId = new Map(response.items.map((coin) => [coin.coin_id, coin]));
        setCoins(coinIds.map((id) => byId.get(id)).filter((coin): coin is MarketCoin => Boolean(coin)));
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(toErrorMessage(err, "Comparison data could not be loaded. Please retry."));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);

  return (
    <section aria-label="Coin comparison" className="rounded-xl border border-sky-200 bg-white p-4 dark:border-sky-900 dark:bg-slate-900">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Compare coins</h2>
        <div className="flex items-center gap-3 text-xs font-medium">
          {coinIds.length > 0 && <button type="button" onClick={onClear} className="text-slate-500 hover:underline dark:text-slate-400">Clear selection</button>}
          <button type="button" onClick={onClose} aria-label="Close comparison" className="rounded p-0.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"><X className="h-4 w-4" aria-hidden="true" /></button>
        </div>
      </div>

      {coinIds.length < 2 && (
        <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          Tick at least two coins in the table to compare them.
        </p>
      )}

      {coinIds.length >= 2 && loading && <div className="h-40 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" aria-label="Loading comparison" />}
      {coinIds.length >= 2 && !loading && error && <RetryError message={error} onRetry={() => setAttempt((v) => v + 1)} />}

      {coinIds.length >= 2 && !loading && !error && coins.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-800">
                <th scope="col" className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-400">Metric</th>
                {coins.map((coin) => (
                  <th key={coin.coin_id} scope="col" className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <CoinLogo src={coin.logo_url} alt="" size={20} />
                      <Link to={`/coins/${coin.coin_id}`} className="font-medium text-slate-800 hover:underline dark:text-slate-100">{coin.symbol.toUpperCase()}</Link>
                      <button type="button" onClick={() => onRemove(coin.coin_id)} aria-label={`Remove ${coin.name} from comparison`} className="rounded p-0.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"><X className="h-3 w-3" aria-hidden="true" /></button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRICS.map((metric) => (
                <tr key={metric.label} className="border-b border-slate-50 last:border-0 dark:border-slate-800">
                  <th scope="row" className="px-3 py-2 text-left text-xs font-medium text-slate-500 dark:text-slate-400">{metric.label}</th>
                  {coins.map((coin) => (
                    <td key={coin.coin_id} className="px-3 py-2 text-right tabular-nums text-slate-700 dark:text-slate-200">{metric.render(coin)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
