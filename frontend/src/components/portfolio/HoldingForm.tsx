import { useState, type FormEvent } from "react";

import type { Holding, HoldingCreate, HoldingUpdate } from "../../types/userFeatures";
import { parseNonNegative, parsePositive } from "../../utils/userInput";
import { CoinPicker, type PickedCoin } from "../common/CoinPicker";
import { TextField } from "../common/FormFields";

interface HoldingFormProps {
  /** When set, the form edits this holding (quantity / average price / notes). Otherwise it records a purchase. */
  editing: Holding | null;
  /** A coin chosen elsewhere (Coin Details), so the user doesn't have to search for it again. */
  initialCoin?: PickedCoin | null;
  saving: boolean;
  error: string | null;
  onAdd: (payload: HoldingCreate) => Promise<boolean>;
  onUpdate: (coinId: string, payload: HoldingUpdate) => Promise<boolean>;
  onClose: () => void;
}

export function HoldingForm({ editing, initialCoin = null, saving, error, onAdd, onUpdate, onClose }: HoldingFormProps) {
  const [coin, setCoin] = useState<PickedCoin | null>(initialCoin);
  const [quantity, setQuantity] = useState(editing ? String(editing.quantity) : "");
  const [price, setPrice] = useState(editing ? String(editing.average_buy_price) : "");
  const [notes, setNotes] = useState(editing?.notes ?? "");
  const [localError, setLocalError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLocalError(null);
    const parsedQuantity = parsePositive(quantity);
    const parsedPrice = parseNonNegative(price);
    if (!editing && !coin) return setLocalError("Choose a coin.");
    if (parsedQuantity === null) return setLocalError("Quantity must be a number greater than 0.");
    if (parsedPrice === null) return setLocalError("Buy price must be a number, 0 or greater.");

    const ok = editing
      ? await onUpdate(editing.coin_id, { quantity: parsedQuantity, average_buy_price: parsedPrice, notes: notes.trim() || null })
      : await onAdd({ coin_id: coin!.id, quantity: parsedQuantity, price: parsedPrice, ...(notes.trim() ? { notes: notes.trim() } : {}) });
    if (ok) onClose();
  }

  const shownError = localError ?? error;
  return (
    <form onSubmit={submit} noValidate aria-label={editing ? "Edit holding" : "Add holding"} className="space-y-3 card card-pad">
      <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
        {editing ? `Edit ${editing.name}` : "Add a holding"}
      </h2>
      {!editing && <CoinPicker selected={coin} onSelect={setCoin} disabled={saving} />}
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField label="Quantity" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="e.g. 0.5" disabled={saving} />
        <TextField
          label={editing ? "Average buy price (USD)" : "Buy price per coin (USD)"}
          inputMode="decimal"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          placeholder="e.g. 45000"
          disabled={saving}
        />
      </div>
      <TextField label="Notes (optional)" value={notes} maxLength={500} onChange={(e) => setNotes(e.target.value)} disabled={saving} />
      {!editing && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          This only records what you hold. It does not buy or sell anything. Adding a coin you already hold merges it using a weighted-average price.
        </p>
      )}
      {shownError && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{shownError}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? "Saving..." : editing ? "Save changes" : "Add holding"}
        </button>
        <button type="button" onClick={onClose} disabled={saving} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}
