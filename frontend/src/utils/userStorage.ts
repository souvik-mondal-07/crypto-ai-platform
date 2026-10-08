/**
 * Small, failure-tolerant localStorage helpers for per-user client-side
 * lists (watchlist, recently viewed, column choices).
 *
 * This is device-local persistence, deliberately NOT presented as server
 * sync: the backend has no watchlist/history API yet. Everything is wrapped
 * in try/catch because storage can be unavailable (private mode, quota) —
 * the UI then simply doesn't persist, it never crashes.
 */
export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Non-fatal: the list just won't persist across reloads.
  }
}

/** Storage key namespaced by user so accounts on one browser don't share lists. */
export function userKey(base: string, userId: string | null | undefined): string {
  return `crypto_ai_platform:${base}:${userId ?? "anonymous"}`;
}
