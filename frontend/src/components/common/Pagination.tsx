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
  const buttonClass = "btn-secondary";

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
