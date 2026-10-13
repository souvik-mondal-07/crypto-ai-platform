import type { Holding } from "../../types/userFeatures";

const COLORS = ["bg-sky-500", "bg-emerald-500", "bg-amber-500", "bg-violet-500", "bg-rose-500", "bg-teal-500", "bg-orange-500", "bg-indigo-500"];
const OTHER_COLOR = "bg-slate-400";
const MAX_SLICES = 7;

/** Asset allocation by current value (priced holdings only). Percentages come from the backend. */
export function AllocationChart({ holdings }: { holdings: Holding[] }) {
  const priced = holdings.filter((holding) => holding.allocation_pct !== null && holding.allocation_pct > 0);
  if (priced.length === 0) return null;

  const top = priced.slice(0, MAX_SLICES);
  const restPct = priced.slice(MAX_SLICES).reduce((sum, holding) => sum + (holding.allocation_pct ?? 0), 0);
  const slices = [
    ...top.map((holding, index) => ({ key: holding.coin_id, label: holding.symbol.toUpperCase(), pct: holding.allocation_pct ?? 0, color: COLORS[index % COLORS.length] })),
    ...(restPct > 0 ? [{ key: "other", label: "Other", pct: restPct, color: OTHER_COLOR }] : []),
  ];

  return (
    <section aria-labelledby="allocation-heading" className="card card-pad">
      <h2 id="allocation-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">Asset allocation</h2>
      <div className="mt-3 flex h-3 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800" role="img" aria-label="Allocation by asset">
        {slices.map((slice) => (
          <div key={slice.key} className={slice.color} style={{ width: `${slice.pct}%` }} title={`${slice.label} ${slice.pct.toFixed(1)}%`} />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3 lg:grid-cols-4">
        {slices.map((slice) => (
          <li key={slice.key} className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
            <span className={`h-2.5 w-2.5 rounded-full ${slice.color}`} aria-hidden="true" />
            <span>{slice.label}</span>
            <span className="ml-auto tabular-nums text-slate-500 dark:text-slate-400">{slice.pct.toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
