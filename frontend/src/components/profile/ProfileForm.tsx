import { useState, type FormEvent } from "react";

import type { Profile } from "../../types/userFeatures";
import { formatAbsoluteDateTime } from "../../utils/formatters";
import { Notice } from "../common/Notice";
import { TextField } from "../common/FormFields";

interface ProfileFormProps {
  profile: Profile;
  onSave: (name: string) => Promise<string | null>;
}

/** Name is editable; email and creation date are read-only (email changes are not part of this phase). */
export function ProfileForm({ profile, onSave }: ProfileFormProps) {
  const [name, setName] = useState(profile.name);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ kind: "success" | "error"; message: string } | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setResult(null);
    const trimmed = name.trim();
    if (!trimmed) return setResult({ kind: "error", message: "Name cannot be blank." });
    if (trimmed.length > 100) return setResult({ kind: "error", message: "Name must be 100 characters or fewer." });
    setSaving(true);
    const error = await onSave(trimmed);
    setSaving(false);
    setResult(error ? { kind: "error", message: error } : { kind: "success", message: "Profile updated." });
  }

  return (
    <form onSubmit={submit} noValidate aria-label="Profile" className="space-y-3 card card-pad">
      <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Profile</h2>
      <TextField label="Name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} disabled={saving} />
      <TextField label="Email" value={profile.email} readOnly disabled />
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Member since {formatAbsoluteDateTime(profile.created_at)}. Your email is your sign-in and can&apos;t be changed here.
      </p>
      {result && <Notice kind={result.kind} message={result.message} />}
      <button type="submit" disabled={saving || name.trim() === profile.name} className="btn-primary">
        {saving ? "Saving..." : "Save changes"}
      </button>
    </form>
  );
}
