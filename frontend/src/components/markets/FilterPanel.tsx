import { SlidersHorizontal, X } from "lucide-react";
import { useState, type ReactNode } from "react";

import {
  CAP_PRESETS,
  CHANGE_PRESETS,
  DEFAULT_SELECTION,
  SUPPLY_OPTIONS,
  VOLUME_PRESETS,
  activeFilterCount,
  type FilterSelection,
} from "../../utils/marketFilters";

interface FilterPanelProps {
  selection: FilterSelection;
  onChange: (next: FilterSelection) => void;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex min-w-[10rem] flex-1 flex-col gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
      {label}
      {children}
    </label>
  );
}

const SELECT =
  "rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-normal text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

/**
 * Advanced filters. Every control maps to a server-side bound (see
 * utils/marketFilters.ts) — selecting one triggers ONE backend request; the
 * browser never filters rows itself. Collapsible so the page stays calm and
 * mobile-friendly; a count badge shows how many filters are active.
 */
export function FilterPanel({ selection, onChange }: FilterPanelProps) {
  const [open, setOpen] = useState(false);
  const count = activeFilterCount(selection);
  const set = <K extends keyof FilterSelection>(key: K, value: FilterSelection[K]) => onChange({ ...selection, [key]: value });

  return (
    <div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
          Filters
          {count > 0 && (
            <span className="rounded-full bg-sky-600 px-1.5 text-xs font-semibold text-white" aria-label={`${count} active`}>
              {count}
            </span>
          )}
        </button>
        {count > 0 && (
          <button type="button" onClick={() => onChange(DEFAULT_SELECTION)} className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:underline dark:text-slate-400">
            <X className="h-3 w-3" aria-hidden="true" /> Clear filters
          </button>
        )}
      </div>

      {open && (
        <div className="mt-3 flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <Field label="Market cap">
            <select value={selection.cap} onChange={(e) => set("cap", e.target.value as FilterSelection["cap"])} className={SELECT}>
              {CAP_PRESETS.map((preset) => <option key={preset.key} value={preset.key}>{preset.label}</option>)}
            </select>
          </Field>
          <Field label="24H change">
            <select value={selection.change} onChange={(e) => set("change", e.target.value as FilterSelection["change"])} className={SELECT}>
              {CHANGE_PRESETS.map((preset) => <option key={preset.key} value={preset.key}>{preset.label}</option>)}
            </select>
          </Field>
          <Field label="24H volume">
            <select value={selection.volume} onChange={(e) => set("volume", e.target.value as FilterSelection["volume"])} className={SELECT}>
              {VOLUME_PRESETS.map((preset) => <option key={preset.key} value={preset.key}>{preset.label}</option>)}
            </select>
          </Field>
          <Field label="Maximum supply">
            <select value={selection.supply} onChange={(e) => set("supply", e.target.value as FilterSelection["supply"])} className={SELECT}>
              {SUPPLY_OPTIONS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
            </select>
          </Field>
        </div>
      )}
    </div>
  );
}
