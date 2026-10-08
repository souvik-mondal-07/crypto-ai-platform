import type { DecisionResponse } from "../../types/decisions";
import {
  formatSignedScore,
  formatWholeNumber,
  riskLevelLabel,
  riskTone,
  TONE_BAR,
  TONE_TEXT,
  type Tone,
} from "../../utils/decisionDisplay";

const CARD = "rounded-lg border border-slate-200 p-3 dark:border-slate-700";
const LABEL = "mb-1 text-xs text-slate-500 dark:text-slate-400";
const NOTE = "mt-1 text-xs text-slate-500 dark:text-slate-400";

function Meter({ label, value, tone }: { label: string; value: number; tone: Tone }) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      className="mt-2 h-2 rounded-full bg-slate-100 dark:bg-slate-800"
    >
      <div className={`h-2 rounded-full ${TONE_BAR[tone]}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Decision score, confidence, risk score and risk level — every number straight from the backend. */
export function DecisionMetrics({ data }: { data: DecisionResponse }) {
  const confidenceKnown = data.confidence !== null && data.confidence_status === "computed";
  const riskKnown = data.risk_score !== null && data.risk_level !== null;
  const tone = riskTone(data.risk_level);

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div className={CARD}>
        <p className={LABEL}>Decision score</p>
        <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{formatSignedScore(data.decision_score)}</p>
        <p className={NOTE}>Scale: -100 (bearish) to +100 (bullish)</p>
      </div>

      <div className={CARD}>
        <p className={LABEL}>Confidence</p>
        {confidenceKnown ? (
          <>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{formatWholeNumber(data.confidence)}%</p>
            <Meter label="Decision confidence" value={data.confidence as number} tone="neutral" />
          </>
        ) : (
          <>
            <p className="text-lg font-semibold text-slate-700 dark:text-slate-200">Unavailable</p>
            <p className={NOTE}>A reliable confidence could not be established from the available signals.</p>
          </>
        )}
      </div>

      <div className={CARD}>
        <p className={LABEL}>Risk score</p>
        {riskKnown ? (
          <>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{formatWholeNumber(data.risk_score)}/100</p>
            <Meter label="Risk score" value={data.risk_score as number} tone={tone} />
          </>
        ) : (
          <p className="text-lg font-semibold text-slate-700 dark:text-slate-200">Unavailable</p>
        )}
      </div>

      <div className={CARD}>
        <p className={LABEL}>Risk level</p>
        <p className={`text-lg font-semibold ${TONE_TEXT[tone]}`}>{riskLevelLabel(data.risk_level)}</p>
        {riskKnown && <p className={NOTE}>{formatWholeNumber(data.risk.coverage_percent)}% of the risk model had data</p>}
      </div>
    </div>
  );
}
