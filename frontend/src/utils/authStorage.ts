/**
 * Centralized token storage — the ONLY place that touches
 * localStorage for authentication. No component or service should
 * call `localStorage` directly for the token; import these functions
 * instead.
 *
 * SECURITY TRADE-OFF (documented, not hidden): storing the JWT in
 * localStorage makes it readable by any JavaScript running on this
 * origin, so it's vulnerable to theft via XSS. The alternative —
 * an HttpOnly cookie issued by the backend — isn't vulnerable to
 * XSS-based token theft, but requires backend changes (Set-Cookie,
 * CSRF protection, SameSite configuration) that are out of scope for
 * this V1. Centralizing access here means that future migration only
 * requires changing this one file (and how the Axios client attaches
 * credentials) — not every place that currently calls getToken().
 */

const TOKEN_KEY = "crypto_ai_platform_access_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    // localStorage can throw (private browsing, disabled storage, etc.)
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Swallow — the user stays logged in for this session via memory
    // (Zustand state) even if persistence fails; next page load will
    // just require logging in again.
  }
}

export function removeToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing meaningful to do if removal fails; the token will be
    // overwritten or expire regardless.
  }
}
