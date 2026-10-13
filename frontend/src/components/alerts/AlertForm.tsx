import { useState, type FormEvent } from "react";

import type { AlertCondition, AlertCreate } from "../../types/userFeatures";
import { parsePositive } from "../../utils/userInput";
import { CoinPicker, type PickedCoin } from "../common/CoinPicker";
import { TextField } from "../common/FormFields";

interface AlertFormProps {
  busy: boolean;
  error: string | null;
  initialCoin?: PickedCoin | null;
  onCreate: (payload: AlertCreate) => Promise<boolean>;
  onClose: () => void;
}

export function AlertForm({ busy, error, initialCoin = null, onCreate, onClose }: AlertFormProps) {
  const [coin, setCoin] = useState<PickedCoin | null>(initialCoin);
  const [condition, setCondition] = useState<AlertCondition>("ABOVE");
  const [target, setTarget] = useState("");
  const [expires, setExpires] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLocalError(null);
    const price = parsePositive(target);
    if (!coin) return setLocalError("Choose a coin.");
    if (price === null) return setLocalError("Target price must be a number greater than 0.");
    let expiresAt: string | undefined;
    if (expires) {
      const date = new Date(`${expires}T23:59:59`);
      if (Number.isNaN(date.getTime()) || date.getTime() <= Date.now()) return setLocalError("Expiry must be a future date.");
      expiresAt = date.toISOString();
    }
    const ok = await onCreate({ coin_id: coin.id, condition, target_price: price, ...(expiresAt ? { expires_at: expiresAt } : {}) });
    if (ok) onClose();
  }

  const shownError = localError ?? error;
  return (
    <form onSubmit={submit} noValidate aria-label="New price alert" className="space-y-3 card card-pad">
      <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">New price alert</h2>
      <CoinPicker selected={coin} onSelect={setCoin} disabled={busy} />
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="alert-condition" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Condition</label>
          <select
            id="alert-condition"
            value={condition}
            onChange={(event) => setCondition(event.target.value as AlertCondition)}
            disabled={busy}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="ABOVE">Price above</option>
            <option value="BELOW">Price below</option>
          </select>
        </div>
        <TextField label="Target price (USD)" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="e.g. 120000" disabled={busy} />
        <TextField label="Expires (optional)" type="date" value={expires} onChange={(e) => setExpires(e.target.value)} disabled={busy} />
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        An alert is only marked triggered when a check against current market data finds the condition true. It never trades.
      </p>
      {shownError && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{shownError}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="btn-primary">
          {busy ? "Saving..." : "Create alert"}
        </button>
        <button type="button" onClick={onClose} disabled={busy} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}
