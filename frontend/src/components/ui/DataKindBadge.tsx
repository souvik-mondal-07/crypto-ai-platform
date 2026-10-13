import { Activity, Brain, ShieldAlert, Sparkles } from "lucide-react";

export type DataKind = "observed" | "model" | "risk" | "ai";

const KINDS: Record<DataKind, { label: string; hint: string; icon: typeof Activity; className: string }> = {
  observed: {
    label: "Observed data",
    hint: "Measured from market and provider data — not a forecast.",
    icon: Activity,
    className: "badge-success",
  },
  model: {
    label: "Model estimate",
    hint: "A statistical model's estimate. It is not a guarantee of any outcome.",
    icon: Brain,
    className: "badge-info",
  },
  risk: {
    label: "Risk assessment",
    hint: "A rule-based risk and decision summary. It is not financial advice.",
    icon: ShieldAlert,
    className: "badge-warning",
  },
  ai: {
    label: "AI-generated",
    hint: "Written by an AI model from the platform's data. It can be wrong; verify before acting.",
    icon: Sparkles,
    className: "badge-neutral",
  },
};

/** Tells the reader what KIND of information a section shows, so observations, estimates and AI text are never confused. */
export function DataKindBadge({ kind }: { kind: DataKind }) {
  const { label, hint, icon: Icon, className } = KINDS[kind];
  return (
    <span className={className} title={hint}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
      <span className="sr-only">. {hint}</span>
    </span>
  );
}
