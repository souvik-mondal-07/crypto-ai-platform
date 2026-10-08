import type { ReactNode } from "react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  message: string;
  action?: ReactNode;
}

/** Shown when a request succeeded but returned no data — never replaced with fake sample data. */
export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-slate-300 py-10 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
      <Inbox className="h-6 w-6" aria-hidden="true" />
      <p className="text-sm">{message}</p>
      {action}
    </div>
  );
}
