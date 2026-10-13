import { useState } from "react";
import { useLocation } from "react-router-dom";
import { BellRing, Plus, RefreshCw } from "lucide-react";

import { AlertForm } from "../components/alerts/AlertForm";
import { AlertsTable } from "../components/alerts/AlertsTable";
import { EmptyState } from "../components/common/EmptyState";
import { TableSkeleton } from "../components/ui/Skeleton";
import { Notice } from "../components/common/Notice";
import { RetryError } from "../components/common/RetryError";
import { AppShell } from "../components/layout/AppShell";
import { useAlerts } from "../hooks/useAlerts";
import { useSettingsStore } from "../store/settingsStore";
import type { PriceAlert } from "../types/userFeatures";
import type { PickedCoin } from "../components/common/CoinPicker";

/** /alerts — the user's price alerts. Checking is explicit and real: it evaluates against stored market data. */
export function Alerts() {
  const { data, loading, error, actionError, busy, checkResult, create, update, remove, check, retry } = useAlerts();
  const showBanner = useSettingsStore((state) => state.settings.notifications.price_alerts);
  // "Set price alert" on Coin Details navigates here with the coin already chosen.
  const presetCoin = (useLocation().state as { alertCoin?: PickedCoin } | null)?.alertCoin ?? null;
  const [creating, setCreating] = useState(presetCoin !== null);

  const triggered = data?.items.filter((alert) => alert.status === "TRIGGERED") ?? [];
  const toggle = (alert: PriceAlert) => void update(alert.id, { status: alert.status === "ACTIVE" ? "DISABLED" : "ACTIVE" });

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Alerts</h1>
          <p className="page-subtitle">Get flagged when a coin&apos;s price crosses a level you choose.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void check()} disabled={busy || loading} className="btn-secondary">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Check now
          </button>
          {!creating && (
            <button type="button" onClick={() => setCreating(true)} className="btn-primary">
              <Plus className="h-4 w-4" aria-hidden="true" />
              New alert
            </button>
          )}
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {showBanner && triggered.length > 0 && (
          <div role="status" className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
            <BellRing className="h-4 w-4" aria-hidden="true" />
            {triggered.length === 1 ? "1 alert has triggered." : `${triggered.length} alerts have triggered.`}
          </div>
        )}
        {checkResult && (
          <Notice
            kind="info"
            message={`Checked ${checkResult.checked} alert${checkResult.checked === 1 ? "" : "s"} against current market data: ${checkResult.triggered} triggered${checkResult.expired ? `, ${checkResult.expired} expired` : ""}${checkResult.skipped_no_price + checkResult.skipped_stale > 0 ? `; ${checkResult.skipped_no_price + checkResult.skipped_stale} skipped (no current price)` : ""}.`}
          />
        )}
        {actionError && !creating && <Notice kind="error" message={actionError} />}
      </div>

      {creating && (
        <div className="mt-4">
          <AlertForm busy={busy} error={actionError} initialCoin={presetCoin} onCreate={create} onClose={() => setCreating(false)} />
        </div>
      )}

      <div className="mt-6">
        {error ? (
          <RetryError message={error} onRetry={retry} />
        ) : loading && data === null ? (
          <TableSkeleton label="Loading your alerts..." rows={5} cols={5} />
        ) : data === null || data.items.length === 0 ? (
          <EmptyState
            message="No alerts configured."
            action={
              !creating ? (
                <button type="button" onClick={() => setCreating(true)} className="btn-primary">
                  Create your first alert
                </button>
              ) : undefined
            }
          />
        ) : (
          <AlertsTable alerts={data.items} busy={busy} onToggle={toggle} onDelete={(alert) => void remove(alert.id)} />
        )}
      </div>
    </AppShell>
  );
}
