import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  page: number;
  pages: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
  /** Used in aria labels, e.g. "news". */
  label?: string;
}

/** Previous / Next pager with an explicit "Page x of y" — works for any paginated list. */
export function Pagination({ page, pages, onPageChange, disabled = false, label = "results" }: PaginationProps) {
  if (pages <= 1) return null;
  const buttonClass =
    "inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800";

  return (
    <nav aria-label={`${label} pagination`} className="mt-4 flex items-center justify-between gap-3">
      <button type="button" className={buttonClass} disabled={disabled || page <= 1} onClick={() => onPageChange(page - 1)}>
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Previous
      </button>
      <span className="text-sm text-slate-600 dark:text-slate-300" aria-live="polite">
        Page {page} of {pages}
      </span>
      <button type="button" className={buttonClass} disabled={disabled || page >= pages} onClick={() => onPageChange(page + 1)}>
        Next
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </button>
    </nav>
  );
}
