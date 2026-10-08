import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import type { SentimentLabel } from "../../types/news";

const STYLES: Record<SentimentLabel, { text: string; classes: string; Icon: typeof Minus }> = {
  positive: {
    text: "Positive",
    classes: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300",
    Icon: TrendingUp,
  },
  neutral: {
    text: "Neutral",
    classes: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    Icon: Minus,
  },
  negative: {
    text: "Negative",
    classes: "bg-red-50 text-red-800 dark:bg-red-950/50 dark:text-red-300",
    Icon: TrendingDown,
  },
};

interface SentimentBadgeProps {
  label: SentimentLabel;
  /** Article score in [-1, 1], shown in the tooltip. */
  score?: number;
}

/** Icon + text (never colour alone) so the label is readable without colour vision. */
export function SentimentBadge({ label, score }: SentimentBadgeProps) {
  const { text, classes, Icon } = STYLES[label];
  const title =
    score === undefined
      ? `${text} news tone`
      : `${text} news tone (score ${score > 0 ? "+" : ""}${score.toFixed(2)} on a −1 to +1 scale)`;
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${classes}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {text}
    </span>
  );
}
