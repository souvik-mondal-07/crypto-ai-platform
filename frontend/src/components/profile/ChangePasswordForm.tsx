import { useState, type FormEvent } from "react";

import type { ChangePasswordPayload } from "../../types/userFeatures";
import { validatePasswordChange } from "../../utils/userInput";
import { PasswordField } from "../common/FormFields";
import { Notice } from "../common/Notice";

interface ChangePasswordFormProps {
  onChange: (payload: ChangePasswordPayload) => Promise<string | null>;
}

export function ChangePasswordForm({ onChange }: ChangePasswordFormProps) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ kind: "success" | "error"; message: string } | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setResult(null);
    const problem = validatePasswordChange({ current, next, confirm });
    if (problem) return setResult({ kind: "error", message: problem });
    setSaving(true);
    const error = await onChange({ current_password: current, new_password: next, confirm_new_password: confirm });
    setSaving(false);
    if (error) return setResult({ kind: "error", message: error });
    setCurrent("");
    setNext("");
    setConfirm("");
    setResult({ kind: "success", message: "Password changed." });
  }

  return (
    <form onSubmit={submit} noValidate aria-label="Change password" className="space-y-3 card card-pad">
      <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Change password</h2>
      <PasswordField label="Current password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} disabled={saving} />
      <PasswordField label="New password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} disabled={saving} />
      <PasswordField label="Confirm new password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} disabled={saving} />
      {result && <Notice kind={result.kind} message={result.message} />}
      <button type="submit" disabled={saving} className="btn-primary">
        {saving ? "Changing..." : "Change password"}
      </button>
    </form>
  );
}
