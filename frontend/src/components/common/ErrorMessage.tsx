import { AlertTriangle } from "lucide-react";

interface ErrorMessageProps {
  message: string;
}

/**
 * User-friendly error display. Never renders raw stack traces —
 * `message` should already be a clean, human-readable string.
 */
export function ErrorMessage({ message }: ErrorMessageProps) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
      <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0" aria-hidden="true" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
