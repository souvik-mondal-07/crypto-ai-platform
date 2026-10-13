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
        className="btn-secondary !min-h-[2rem] !py-1 text-xs !text-sky-700 dark:!text-sky-300"
      >
        <RefreshCw className="h-3 w-3" aria-hidden="true" />
        Retry
      </button>
    </div>
  );
}
