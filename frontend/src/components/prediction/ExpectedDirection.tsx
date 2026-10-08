import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import type { PredictionDirection } from "../../types/predictions";

const STYLES: Record<PredictionDirection, { text: string; classes: string; Icon: typeof Minus }> = {
  up: { text: "Up", classes: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300", Icon: TrendingUp },
  down: { text: "Down", classes: "bg-red-50 text-red-800 dark:bg-red-950/50 dark:text-red-300", Icon: TrendingDown },
  flat: { text: "No clear direction", classes: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300", Icon: Minus },
};

/** Icon + text, so direction is never conveyed by colour alone. */
export function ExpectedDirection({ direction }: { direction: PredictionDirection }) {
  const { text, classes, Icon } = STYLES[direction];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-semibold ${classes}`}>
      <Icon className="h-4 w-4" aria-hidden="true" />
      {text}
    </span>
  );
}
