import { useState } from "react";
import { useLocation } from "react-router-dom";
import { Plus } from "lucide-react";

import { EmptyState } from "../../components/common/EmptyState";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { RetryError } from "../../components/common/RetryError";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { AppShell } from "../../components/layout/AppShell";
import { AllocationChart } from "../../components/portfolio/AllocationChart";
import { HoldingForm } from "../../components/portfolio/HoldingForm";
import { HoldingsTable } from "../../components/portfolio/HoldingsTable";
import { PortfolioSummaryCards } from "../../components/portfolio/PortfolioSummaryCards";
import { usePortfolio } from "../../hooks/usePortfolio";
import type { Holding } from "../../types/userFeatures";
import type { PickedCoin } from "../../components/common/CoinPicker";

type FormState = { mode: "closed" } | { mode: "add" } | { mode: "edit"; holding: Holding };

/**
 * /portfolio — the user's RECORDED holdings valued at current market prices. Tracking only: nothing here
 * places an order or touches an exchange.
 */
export function Portfolio() {
  const { portfolio, status, error, saving, actionError, load, userId, addHolding, updateHolding, removeHolding, clearActionError } =
    usePortfolio();
  // "Add to Portfolio" on Coin Details navigates here with the coin already chosen.
  const presetCoin = (useLocation().state as { addCoin?: PickedCoin } | null)?.addCoin ?? null;
  const [form, setForm] = useState<FormState>(presetCoin ? { mode: "add" } : { mode: "closed" });
  const [confirmRemove, setConfirmRemove] = useState<Holding | null>(null);

  const closeForm = () => {
    clearActionError();
    setForm({ mode: "closed" });
  };

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Portfolio</h1>
          <p className="page-subtitle">
            Track what you hold, valued at current market prices. Records only — no trades are executed.
          </p>
        </div>
        {form.mode === "closed" && status === "ready" && (
          <button
            type="button"
            onClick={() => setForm({ mode: "add" })}
            className="btn-primary"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add holding
          </button>
        )}
      </div>

      {form.mode !== "closed" && (
        <div className="mt-4">
          <HoldingForm
            key={form.mode === "edit" ? form.holding.coin_id : "add"}
            editing={form.mode === "edit" ? form.holding : null}
            initialCoin={presetCoin}
            saving={saving}
            error={actionError}
            onAdd={addHolding}
            onUpdate={updateHolding}
            onClose={closeForm}
          />
        </div>
      )}

      {confirmRemove && (
        <ConfirmDialog
          title={`Remove ${confirmRemove.name}?`}
          confirmLabel="Remove"
          destructive
          busy={saving}
          onCancel={() => setConfirmRemove(null)}
          onConfirm={async () => {
            await removeHolding(confirmRemove.coin_id);
            setConfirmRemove(null);
          }}
        >
          This removes {confirmRemove.name} and its recorded purchases from your portfolio. It does not sell anything.
        </ConfirmDialog>
      )}
      {actionError && form.mode === "closed" && (
        <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">{actionError}</p>
      )}

      <div className="mt-6 space-y-4">
        {status === "error" ? (
          <RetryError message={error ?? "Your portfolio could not be loaded."} onRetry={() => void load(userId)} />
        ) : status !== "ready" || portfolio === null ? (
          <TableSkeleton label="Loading your portfolio..." rows={5} cols={5} />
        ) : portfolio.holdings.length === 0 ? (
          <EmptyState
            message="Your portfolio is empty. Add your first holding to start tracking performance."
            action={
              form.mode === "closed" ? (
                <button type="button" onClick={() => setForm({ mode: "add" })} className="btn-primary">
                  Add your first holding
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            <PortfolioSummaryCards summary={portfolio.summary} />
            <AllocationChart holdings={portfolio.holdings} />
            <HoldingsTable
              holdings={portfolio.holdings}
              disabled={saving}
              onEdit={(holding) => {
                clearActionError();
                setForm({ mode: "edit", holding });
              }}
              onRemove={setConfirmRemove}
            />
          </>
        )}
      </div>
    </AppShell>
  );
}
