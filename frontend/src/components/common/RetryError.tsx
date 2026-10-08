import { RefreshCw } from "lucide-react";

import { ErrorMessage } from "./ErrorMessage";

interface RetryErrorProps {
  message: string;
  onRetry: () => void;
  /** Smaller layout for compact widgets. */
  compact?: boolean;
}

/**
 * The standard error treatment for every data section: a clean message (never
 * a stack trace — callers pass the already-classified message from
 * utils/apiErrors.ts) plus a Retry button, so no section is ever a dead end.
 */
export function RetryError({ message, onRetry, compact = false }: RetryErrorProps) {
  return (
    <div role="alert" className={compact ? "space-y-2" : "space-y-3"}>
      <ErrorMessage message={message} />
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-sky-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:text-sky-400 dark:hover:bg-slate-800"
      >
        <RefreshCw className="h-3 w-3" aria-hidden="true" />
        Retry
      </button>
    </div>
  );
}
