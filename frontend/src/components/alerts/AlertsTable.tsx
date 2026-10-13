import { Link } from "react-router-dom";
import { Power, Trash2 } from "lucide-react";

import type { AlertStatus, PriceAlert } from "../../types/userFeatures";
import { formatAbsoluteDateTime, formatRelativeTime, formatUsd } from "../../utils/formatters";
import { CoinLogo } from "../market/CoinLogo";

const STATUS_STYLES: Record<AlertStatus, string> = {
  ACTIVE: "bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300",
  TRIGGERED: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  DISABLED: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  EXPIRED: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
};

interface AlertsTableProps {
  alerts: PriceAlert[];
  busy: boolean;
  onToggle: (alert: PriceAlert) => void;
  onDelete: (alert: PriceAlert) => void;
}

export function AlertsTable({ alerts, busy, onToggle, onDelete }: AlertsTableProps) {
  return (
    <div className="overflow-x-auto card">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <th className="px-4 py-3 font-medium">Coin</th>
            <th className="px-3 py-3 font-medium">Condition</th>
            <th className="px-3 py-3 text-right font-medium">Current price</th>
            <th className="px-3 py-3 font-medium">Status</th>
            <th className="px-3 py-3 font-medium">Details</th>
            <th className="px-3 py-3"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => (
            <tr key={alert.id} className="border-b border-slate-50 last:border-0 dark:border-slate-800">
              <td className="px-4 py-3">
                <Link to={`/coins/${alert.coin_id}`} className="flex items-center gap-2 font-medium text-slate-800 hover:underline dark:text-slate-100">
                  <CoinLogo src={alert.logo_url} alt="" />
                  <span className="max-w-[160px] truncate">{alert.name ?? "Unknown coin"}</span>
                  {alert.symbol && <span className="text-xs text-slate-400">{alert.symbol.toUpperCase()}</span>}
                </Link>
              </td>
              <td className="px-3 py-3 tabular-nums text-slate-700 dark:text-slate-200">
                Price {alert.condition === "ABOVE" ? "above" : "below"} {formatUsd(alert.target_price)}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">{alert.current_price === null ? <span className="text-slate-400">N/A</span> : formatUsd(alert.current_price)}</td>
              <td className="px-3 py-3"><span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLES[alert.status]}`}>{alert.status.charAt(0) + alert.status.slice(1).toLowerCase()}</span></td>
              <td className="px-3 py-3 text-xs text-slate-500 dark:text-slate-400">
                {alert.status === "TRIGGERED" && alert.triggered_at && (
                  <span title={formatAbsoluteDateTime(alert.triggered_at)}>Triggered {formatRelativeTime(alert.triggered_at)} at {formatUsd(alert.triggered_price)}</span>
                )}
                {alert.status !== "TRIGGERED" && alert.expires_at && <span>Expires {formatAbsoluteDateTime(alert.expires_at)}</span>}
                {alert.status === "ACTIVE" && !alert.expires_at && alert.last_checked_at && <span>Last checked {formatRelativeTime(alert.last_checked_at)}</span>}
              </td>
              <td className="px-3 py-3 text-right whitespace-nowrap">
                <button
                  type="button"
                  onClick={() => onToggle(alert)}
                  disabled={busy}
                  aria-label={alert.status === "ACTIVE" ? `Disable alert for ${alert.name ?? "coin"}` : `Re-enable alert for ${alert.name ?? "coin"}`}
                  title={alert.status === "ACTIVE" ? "Disable" : "Re-enable"}
                  className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-40 dark:hover:bg-slate-800"
                >
                  <Power className="h-4 w-4" aria-hidden="true" />
                </button>
                <button type="button" onClick={() => onDelete(alert)} disabled={busy} aria-label={`Delete alert for ${alert.name ?? "coin"}`} className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-40 dark:hover:bg-slate-800">
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
