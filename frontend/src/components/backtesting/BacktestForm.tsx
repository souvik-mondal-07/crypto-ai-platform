import { useMemo, useState, type FormEvent } from "react";
import { X } from "lucide-react";

import { CoinPicker, type PickedCoin } from "../common/CoinPicker";
import { Notice } from "../common/Notice";
import type { BacktestConfig, BacktestRequest, BarInterval, SizingMode } from "../../types/backtesting";
import { buildBacktestRequest } from "../../utils/backtestRequest";

interface BacktestFormProps {
  config: BacktestConfig;
  submitting: boolean;
  submitError: string | null;
  onSubmit: (request: BacktestRequest) => void | Promise<unknown>;
}

const INPUT =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";
const LABEL = "mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200";

const isoDay = (date: Date) => date.toISOString().slice(0, 10);

/** Backtest configuration: every default and limit comes from the API's /config, none is hard-coded here. */
export function BacktestForm({ config, submitting, submitError, onSubmit }: BacktestFormProps) {
  const d = config.defaults;
  const initialEnd = useMemo(() => new Date(), []);
  const [coins, setCoins] = useState<PickedCoin[]>([]);
  const [pickerKey, setPickerKey] = useState(0);
  const [start, setStart] = useState(() => isoDay(new Date(initialEnd.getTime() - 30 * 86_400_000)));
  const [end, setEnd] = useState(() => isoDay(new Date(initialEnd.getTime() - 86_400_000)));
  const [capital, setCapital] = useState(String(d.starting_capital));
  const [barInterval, setBarInterval] = useState<BarInterval>(d.bar_interval);
  const [sizingMode, setSizingMode] = useState<SizingMode>(d.sizing_mode);
  const [positionSize, setPositionSize] = useState(String(d.sizing_mode === "fixed_fraction" ? d.position_size * 100 : d.position_size));
  const [maxAllocationPct, setMaxAllocationPct] = useState(String(d.max_allocation_pct * 100));
  const [feePct, setFeePct] = useState(String(Number((d.fee_rate * 100).toFixed(4))));
  const [slippagePct, setSlippagePct] = useState(String(Number((d.slippage_rate * 100).toFixed(4))));
  const [closeAtEnd, setCloseAtEnd] = useState(d.close_open_positions_at_end);
  const [validation, setValidation] = useState<string | null>(null);

  const zeroCosts = Number(feePct) === 0 && Number(slippagePct) === 0;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const built = buildBacktestRequest({ coins, start, end, capital, interval: barInterval, sizingMode, positionSize, maxAllocationPct, feePct, slippagePct, closeAtEnd }, config);
    if ("error" in built) {
      setValidation(built.error);
      return;
    }
    setValidation(null);
    void onSubmit(built.request);
  };

  const changeSizingMode = (mode: SizingMode) => {
    setSizingMode(mode);
    setPositionSize(mode === "fixed_fraction" ? String(d.position_size * 100) : String(Math.min(Number(capital) || d.starting_capital, d.starting_capital) / 4));
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4" aria-label="Backtest configuration">
      <div>
        <span className={LABEL}>Coins (up to {config.limits.max_coins})</span>
        {coins.length > 0 && (
          <ul className="mb-2 flex flex-wrap gap-2" aria-label="Selected coins">
            {coins.map((coin) => (
              <li key={coin.id} className="badge-neutral gap-1.5">
                {coin.name} <span className="text-slate-400">{coin.symbol.toUpperCase()}</span>
                <button type="button" aria-label={`Remove ${coin.name}`} disabled={submitting} onClick={() => setCoins(coins.filter((c) => c.id !== coin.id))}>
                  <X className="h-3 w-3" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
        {coins.length < config.limits.max_coins && (
          <CoinPicker
            key={pickerKey}
            label="Add a coin"
            selected={null}
            disabled={submitting}
            onSelect={(coin) => {
              if (coin && !coins.some((c) => c.id === coin.id)) setCoins([...coins, coin]);
              setPickerKey((value) => value + 1);
            }}
          />
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label><span className={LABEL}>Start date</span><input type="date" className={INPUT} value={start} onChange={(e) => setStart(e.target.value)} disabled={submitting} /></label>
        <label><span className={LABEL}>End date</span><input type="date" className={INPUT} value={end} onChange={(e) => setEnd(e.target.value)} disabled={submitting} /></label>
        <label><span className={LABEL}>Starting capital (USD)</span><input type="number" min="0" step="any" inputMode="decimal" className={INPUT} value={capital} onChange={(e) => setCapital(e.target.value)} disabled={submitting} /></label>
        <label>
          <span className={LABEL}>Bar interval</span>
          <select className={INPUT} value={barInterval} onChange={(e) => setBarInterval(e.target.value as BarInterval)} disabled={submitting}>
            {config.bar_intervals.map((i) => <option key={i} value={i}>{i}</option>)}
          </select>
        </label>
        <label>
          <span className={LABEL}>Position sizing</span>
          <select className={INPUT} value={sizingMode} onChange={(e) => changeSizingMode(e.target.value as SizingMode)} disabled={submitting}>
            <option value="fixed_fraction">Fixed % of equity per entry</option>
            <option value="fixed_amount">Fixed USD amount per entry</option>
          </select>
        </label>
        <label>
          <span className={LABEL}>{sizingMode === "fixed_fraction" ? "Position size (% of equity)" : "Position size (USD)"}</span>
          <input type="number" min="0" step="any" inputMode="decimal" className={INPUT} value={positionSize} onChange={(e) => setPositionSize(e.target.value)} disabled={submitting} />
        </label>
        <label><span className={LABEL}>Max allocation per asset (%)</span><input type="number" min="0" max="100" step="any" inputMode="decimal" className={INPUT} value={maxAllocationPct} onChange={(e) => setMaxAllocationPct(e.target.value)} disabled={submitting} /></label>
        <label><span className={LABEL}>Transaction fee (% per side)</span><input type="number" min="0" step="any" inputMode="decimal" className={INPUT} value={feePct} onChange={(e) => setFeePct(e.target.value)} disabled={submitting} /></label>
        <label><span className={LABEL}>Slippage (% per fill)</span><input type="number" min="0" step="any" inputMode="decimal" className={INPUT} value={slippagePct} onChange={(e) => setSlippagePct(e.target.value)} disabled={submitting} /></label>
        <label>
          <span className={LABEL}>Benchmark</span>
          <select className={INPUT} value={d.benchmark} disabled aria-label="Benchmark">
            <option value={d.benchmark}>Equal-weight buy &amp; hold (same costs)</option>
          </select>
        </label>
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
        <input type="checkbox" checked={closeAtEnd} onChange={(e) => setCloseAtEnd(e.target.checked)} disabled={submitting} />
        Close open positions at the end of the period
      </label>

      <p className="text-xs text-slate-500 dark:text-slate-400">{config.strategy_description}</p>
      {zeroCosts && <Notice kind="info" message="Fees and slippage are both set to 0%. Results will be optimistic; real trading always has costs." />}
      {validation && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{validation}</p>}
      {submitError && <Notice kind="error" message={submitError} />}

      <button type="submit" className="btn-primary" disabled={submitting}>
        {submitting ? "Starting backtest..." : "Run backtest"}
      </button>
    </form>
  );
}
