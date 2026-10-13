import type { ReactNode } from "react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  message: string;
  action?: ReactNode;
}

/** Shown when a request succeeded but returned no data — never replaced with fake sample data. */
export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-dashed border-slate-300 px-4 py-10 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800">
        <Inbox className="h-5 w-5" aria-hidden="true" />
      </span>
      <p className="max-w-md text-sm">{message}</p>
      {action}
    </div>
  );
}
