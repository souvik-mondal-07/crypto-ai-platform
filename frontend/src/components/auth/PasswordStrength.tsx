import { Check, Circle } from "lucide-react";

export const MIN_PASSWORD_LENGTH = 8;

export interface StrengthResult {
  /** 0–4 */
  score: number;
  label: "Too short" | "Weak" | "Fair" | "Good" | "Strong";
  checks: { id: string; label: string; ok: boolean; required: boolean }[];
}

/**
 * Honest, client-side strength estimate from simple, explainable rules (length, mixed case, a digit, a symbol).
 * Only the minimum length is REQUIRED (it mirrors the backend rule); the rest are recommendations, and the
 * wording says so. It never claims a password is "secure" — just how many good practices it follows.
 */
export function assessPassword(password: string): StrengthResult {
  const long = password.length >= MIN_PASSWORD_LENGTH;
  const longer = password.length >= 12;
  const mixed = /[a-z]/.test(password) && /[A-Z]/.test(password);
  const digit = /\d/.test(password);
  const symbol = /[^A-Za-z0-9]/.test(password);

  const checks = [
    { id: "length", label: `At least ${MIN_PASSWORD_LENGTH} characters`, ok: long, required: true },
    { id: "case", label: "Upper and lower case letters", ok: mixed, required: false },
    { id: "digit", label: "A number", ok: digit, required: false },
    { id: "symbol", label: "A symbol", ok: symbol, required: false },
  ];

  if (!long) return { score: password.length === 0 ? 0 : 1, label: password.length === 0 ? "Too short" : "Too short", checks };

  const points = [mixed, digit, symbol, longer].filter(Boolean).length; // 0..4
  const score = Math.min(4, Math.max(1, points + 0)) as 1 | 2 | 3 | 4;
  const label = score === 1 ? "Weak" : score === 2 ? "Fair" : score === 3 ? "Good" : "Strong";
  return { score, label, checks };
}

const BAR_COLORS = ["bg-slate-600", "bg-red-500", "bg-amber-500", "bg-sky-400", "bg-emerald-400"];

export function PasswordStrength({ password }: { password: string }) {
  const { score, label, checks } = assessPassword(password);
  const shown = password.length > 0;

  return (
    <div className="mt-3" aria-live="polite">
      <div className="flex items-center gap-1.5" aria-hidden="true">
        {[1, 2, 3, 4].map((segment) => (
          <span key={segment} className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
            <span
              className={`block h-full origin-left rounded-full transition-transform duration-500 ease-out ${BAR_COLORS[score]} ${shown && segment <= score ? "scale-x-100" : "scale-x-0"}`}
            />
          </span>
        ))}
      </div>
      <p className="mt-1.5 text-xs text-slate-400">
        {shown ? (
          <>
            Password strength: <span className="font-medium text-slate-200">{label}</span>
          </>
        ) : (
          "Choose a password — the longer, the better."
        )}
      </p>
      <ul className="mt-2 grid gap-1 text-xs sm:grid-cols-2">
        {checks.map((check) => (
          <li key={check.id} className={`flex items-center gap-1.5 transition-colors duration-200 ${check.ok ? "text-emerald-300" : "text-slate-500"}`}>
            {check.ok ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Circle className="h-3 w-3" aria-hidden="true" />}
            <span>
              {check.label}
              {!check.required && <span className="text-slate-500"> (recommended)</span>}
            </span>
            <span className="sr-only">{check.ok ? " — met" : check.required ? " — required, not met yet" : " — not met"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
