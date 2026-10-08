/**
 * Centralized environment configuration.
 *
 * All environment-driven values must be read through this module —
 * never reference `import.meta.env` directly elsewhere in the app.
 */

function requireEnv(key: string, fallback?: string): string {
  const value = import.meta.env[key] ?? fallback;
  if (value === undefined) {
    // Fail loudly in dev rather than silently falling back to a
    // hard-coded URL somewhere deep in a component.
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
}

export const env = {
  apiBaseUrl: requireEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1"),
  // Frontend auto-refresh polling interval, added by the real-time
  // refresh upgrade. Deliberately its own setting rather than reusing the API
  // client's request timeout: this controls how often we re-ask for
  // data, not how long any single request is allowed to take.
  marketRefreshIntervalMs: Number(
    requireEnv("VITE_MARKET_REFRESH_INTERVAL_MS", "20000"),
  ),
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const;
