import { Link } from "react-router-dom";
import { Wallet } from "lucide-react";

import { useAuthStore } from "../../store/authStore";
import { usePortfolioStore } from "../../store/portfolioStore";
import { changeColorClass, formatPercent, formatUsd } from "../../utils/formatters";
import { Metric } from "./MarketSnapshot";

/**
 * "Portfolio Value" statistic card: the signed-in user's total current value from GET /portfolio (calculated by the
 * backend) with the unrealised P/L %. Signed out, still loading, failed or empty → "N/A" with a plain explanation;
 * never a made-up number.
 */
export function PortfolioValueCard() {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const portfolio = usePortfolioStore((state) => state.portfolio);
  const status = usePortfolioStore((state) => state.status);

  const hasHoldings = !!portfolio && portfolio.holdings.length > 0;
  const value = userId && portfolio && hasHoldings ? formatUsd(portfolio.summary.total_current_value) : "N/A";
  const pct = userId && portfolio && hasHoldings ? portfolio.summary.total_unrealized_pnl_pct : null;

  let footer;
  if (!userId) footer = <span className="text-slate-500 dark:text-slate-400">Sign in to see your portfolio</span>;
  else if (status === "error") footer = <span className="text-slate-500 dark:text-slate-400">Could not be loaded</span>;
  else if (status === "ready" && !hasHoldings) {
    footer = (
      <Link to="/portfolio" className="text-sky-600 hover:underline dark:text-sky-400">
        Add your first holding
      </Link>
    );
  } else if (pct !== null && pct !== undefined) {
    footer = <span className={`font-medium tabular-nums ${changeColorClass(pct)}`}>{formatPercent(pct)} P/L</span>;
  } else footer = <span className="text-slate-500 dark:text-slate-400">{status === "ready" ? "P/L unavailable" : "Loading…"}</span>;

  return (
    <Metric label="Portfolio Value" icon={Wallet} tone="violet" footer={footer}>
      {value}
    </Metric>
  );
}
