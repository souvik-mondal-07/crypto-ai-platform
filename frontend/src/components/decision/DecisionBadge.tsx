import type { DecisionValue } from "../../types/decisions";
import { decisionTone, TONE_BADGE } from "../../utils/decisionDisplay";

/** The decision word, with a text label as well as colour (never colour-only). */
export function DecisionBadge({ decision }: { decision: DecisionValue }) {
  return (
    <span
      aria-label={`Model-based decision: ${decision}`}
      className={`inline-flex items-center rounded-lg border px-4 py-1.5 text-2xl font-bold tracking-wide ${TONE_BADGE[decisionTone(decision)]}`}
    >
      {decision}
    </span>
  );
}
