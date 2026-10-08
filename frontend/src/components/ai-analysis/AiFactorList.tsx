import { AlertTriangle, CheckCircle2, HelpCircle, ShieldAlert } from "lucide-react";

export type AiFactorKind = "bullish" | "bearish" | "risks" | "uncertainties";

const CONFIG = {
  bullish: { title: "Bullish Factors", empty: "No bullish factors were identified in the supplied data.", Icon: CheckCircle2, icon: "text-emerald-600 dark:text-emerald-400" },
  bearish: { title: "Bearish Factors", empty: "No bearish factors were identified in the supplied data.", Icon: AlertTriangle, icon: "text-red-600 dark:text-red-400" },
  risks: { title: "Key Risks", empty: "No key risks were highlighted.", Icon: ShieldAlert, icon: "text-amber-600 dark:text-amber-400" },
  uncertainties: { title: "Uncertainties", empty: "No specific uncertainties were highlighted.", Icon: HelpCircle, icon: "text-slate-500 dark:text-slate-400" },
} as const;

interface AiFactorListProps {
  kind: AiFactorKind;
  items: string[];
}

/** AI-written points, each tied by the model to the platform's supplied data. Plain text only. */
export function AiFactorList({ kind, items }: AiFactorListProps) {
  const { title, empty, Icon, icon } = CONFIG[kind];
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{title}</h4>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">{empty}</p>
      ) : (
        <ul className="space-y-1.5" aria-label={title}>
          {items.map((item, index) => (
            <li key={`${index}-${item}`} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${icon}`} aria-hidden="true" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
