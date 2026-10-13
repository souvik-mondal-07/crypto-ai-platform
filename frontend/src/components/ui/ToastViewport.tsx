import { useEffect } from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";

import { useToastStore, type Toast } from "../../store/toastStore";

const AUTO_DISMISS_MS = 4500;
const ERROR_DISMISS_MS = 7000;

const STYLES = {
  success: "border-emerald-200 text-emerald-900 dark:border-emerald-900 dark:text-emerald-200",
  info: "border-sky-200 text-sky-900 dark:border-sky-900 dark:text-sky-200",
  error: "border-red-200 text-red-900 dark:border-red-900 dark:text-red-200",
} as const;

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((state) => state.dismiss);
  const Icon = toast.kind === "success" ? CheckCircle2 : toast.kind === "error" ? XCircle : Info;

  useEffect(() => {
    const timer = window.setTimeout(() => dismiss(toast.id), toast.kind === "error" ? ERROR_DISMISS_MS : AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [dismiss, toast.id, toast.kind]);

  return (
    <li
      className={`pointer-events-auto flex items-start gap-2 rounded-lg border bg-white px-3 py-2.5 text-sm shadow-pop animate-toast-in motion-reduce:animate-none dark:bg-slate-900 ${STYLES[toast.kind]}`}
    >
      <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <span className="flex-1">{toast.message}</span>
      <button type="button" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification" className="rounded p-0.5 opacity-60 hover:opacity-100">
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </li>
  );
}

/**
 * Fixed notification stack. One polite live region (so screen readers announce each message once);
 * it never takes focus and never blocks the page beneath it.
 */
export function ToastViewport() {
  const toasts = useToastStore((state) => state.toasts);
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-4 sm:inset-x-auto sm:right-4 sm:justify-end sm:px-0" aria-live="polite" aria-atomic="false">
      <ul className="flex w-full max-w-sm flex-col gap-2">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} />
        ))}
      </ul>
    </div>
  );
}
