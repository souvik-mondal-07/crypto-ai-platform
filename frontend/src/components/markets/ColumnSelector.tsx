import { useEffect, useRef, useState } from "react";
import { Settings2 } from "lucide-react";

import { COLUMNS, type ColumnKey } from "../../utils/marketColumns";

interface ColumnSelectorProps {
  visible: ColumnKey[];
  onToggle: (key: ColumnKey) => void;
  onReset: () => void;
}

/** "Columns" menu. Price/24H etc. can be hidden; Rank and Coin are always shown. */
export function ColumnSelector({ visible, onToggle, onReset }: ColumnSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="true"
        aria-expanded={open}
        title="Choose visible columns"
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
      >
        <Settings2 className="h-4 w-4" aria-hidden="true" />
        Columns
      </button>
      {open && (
        <div role="group" aria-label="Visible columns" className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-slate-200 bg-white p-2 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          {COLUMNS.map((column) => (
            <label key={column.key} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800">
              <input
                type="checkbox"
                checked={visible.includes(column.key)}
                onChange={() => onToggle(column.key)}
                className="h-4 w-4 rounded border-slate-300"
              />
              {column.label}
            </label>
          ))}
          <button type="button" onClick={onReset} className="mt-1 w-full rounded px-2 py-1.5 text-left text-xs font-medium text-sky-600 hover:bg-slate-50 dark:text-sky-400 dark:hover:bg-slate-800">
            Reset to default
          </button>
        </div>
      )}
    </div>
  );
}
