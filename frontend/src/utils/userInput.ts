/**
 * Small, pure parsers for the user-feature forms. They only give fast feedback — the backend (Pydantic)
 * re-validates everything and is the real authority.
 */

/** Parses a positive-or-zero decimal typed by the user. Returns null for blank, NaN, Infinity, or negatives. */
export function parseNonNegative(raw: string): number | null {
  const text = raw.trim();
  if (text === "") return null;
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

/** Strictly greater than zero. */
export function parsePositive(raw: string): number | null {
  const value = parseNonNegative(raw);
  return value !== null && value > 0 ? value : null;
}

export interface PasswordFormValues {
  current: string;
  next: string;
  confirm: string;
}

/** Client-side mirror of the backend's change-password rules (8–128 chars, confirmation matches, not unchanged). */
export function validatePasswordChange({ current, next, confirm }: PasswordFormValues): string | null {
  if (!current) return "Enter your current password.";
  if (next.length < 8) return "The new password must be at least 8 characters.";
  if (next.length > 128) return "The new password must be at most 128 characters.";
  if (next !== confirm) return "The new passwords do not match.";
  if (next === current) return "The new password must be different from the current password.";
  return null;
}
