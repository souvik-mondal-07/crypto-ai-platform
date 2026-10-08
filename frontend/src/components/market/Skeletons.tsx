/** Skeleton placeholders shown while market data loads — never a blank screen. */

export function SkeletonRow() {
  return (
    <tr className="animate-pulse border-b border-slate-50 dark:border-slate-800">
      <td className="px-4 py-3">
        <div className="h-3 w-6 rounded bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-slate-200 dark:bg-slate-800" />
          <div className="h-3 w-24 rounded bg-slate-200 dark:bg-slate-800" />
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="h-3 w-12 rounded bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 w-16 rounded bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 w-12 rounded bg-slate-200 dark:bg-slate-800" />
      </td>
    </tr>
  );
}

export function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="h-3 w-20 rounded bg-slate-200 dark:bg-slate-800" />
      <div className="mt-3 h-5 w-28 rounded bg-slate-200 dark:bg-slate-800" />
    </div>
  );
}

export function SkeletonMoverCard() {
  return (
    <div className="flex animate-pulse items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2 dark:border-slate-800">
      <div className="flex items-center gap-2">
        <div className="h-7 w-7 rounded-full bg-slate-200 dark:bg-slate-800" />
        <div className="h-3 w-20 rounded bg-slate-200 dark:bg-slate-800" />
      </div>
      <div className="h-3 w-12 rounded bg-slate-200 dark:bg-slate-800" />
    </div>
  );
}
