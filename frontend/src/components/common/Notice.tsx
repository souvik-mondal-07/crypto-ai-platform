import { CheckCircle2, Info, XCircle, X } from "lucide-react";

interface NoticeProps {
  kind: "success" | "info" | "error";
  message: string;
  onDismiss?: () => void;
}

const STYLES = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300",
  info: "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-300",
  error: "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300",
} as const;

/** A short, dismissible status message (success / already-exists / failure). Never carries raw error detail. */
export function Notice({ kind, message, onDismiss }: NoticeProps) {
  const Icon = kind === "success" ? CheckCircle2 : kind === "error" ? XCircle : Info;
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${STYLES[kind]}`}
    >
      <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <p className="flex-1">{message}</p>
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Dismiss message" className="rounded p-0.5 hover:opacity-70">
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
