import type { DecisionResponse } from "../../types/decisions";
import { riskLevelLabel, riskTone, signalLabel, signalTone, TONE_TEXT, type Tone } from "../../utils/decisionDisplay";

interface Row {
  key: string;
  label: string;
  value: string;
  tone: Tone;
}

/** Compact "what each module says" summary — only real module outputs, no placeholders. */
export function SignalSummary({ data }: { data: DecisionResponse }) {
  const s = data.signals;
  const rows: Row[] = [
    { key: "technical", label: "Technical", value: signalLabel(s.technical), tone: signalTone(s.technical) },
    { key: "fundamental", label: "Fundamental", value: signalLabel(s.fundamental), tone: signalTone(s.fundamental) },
    { key: "sentiment", label: "Sentiment", value: signalLabel(s.sentiment), tone: signalTone(s.sentiment) },
    { key: "prediction", label: "ML Prediction", value: signalLabel(s.prediction), tone: signalTone(s.prediction) },
    { key: "risk", label: "Risk", value: data.risk_level ? riskLevelLabel(data.risk_level) : "Unavailable", tone: riskTone(data.risk_level) },
  ];

  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Signal summary</h3>
      <dl className="divide-y divide-slate-100 rounded-lg border border-slate-200 dark:divide-slate-800 dark:border-slate-700">
        {rows.map((row) => (
          <div key={row.key} className="flex items-center justify-between px-3 py-2 text-sm">
            <dt className="text-slate-600 dark:text-slate-300">{row.label}</dt>
            <dd className={`font-medium ${TONE_TEXT[row.tone]}`}>{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
