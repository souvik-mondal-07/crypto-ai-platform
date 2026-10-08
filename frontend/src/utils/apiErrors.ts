import { ApiError } from "../types/apiError";

export type ErrorKind = "network" | "timeout" | "rate_limited" | "server" | "unavailable" | "client" | "unknown";

/**
 * Turns whatever a failed request threw into a short, user-safe message and a
 * category the UI can branch on (e.g. to hide "Retry now" while rate limited).
 *
 * Distinguishes:
 *  - network failure (no HTTP response at all — the old blanket "Network Error")
 *  - timeout
 *  - 429 provider/API rate limit
 *  - 5xx server error
 *  - 4xx API error (the backend's own clean message is used)
 *
 * Raw stack traces are never exposed: only `ApiError.message` (already the
 * backend's clean message) or a fixed string below is returned. Plain `Error`s
 * (e.g. the store's own "took too long" guard) keep their message.
 */
export function classifyError(error: unknown, fallback = "Market data could not be loaded. Please retry."): {
  kind: ErrorKind;
  message: string;
} {
  if (error instanceof ApiError) {
    const { status } = error;

    if (status === undefined) {
      if (/timeout|timed out/i.test(error.message)) {
        return { kind: "timeout", message: "The request took too long. Please retry." };
      }
      return {
        kind: "network",
        message: "Unable to reach the server. Check your connection and retry.",
      };
    }
    if (status === 429) {
      return {
        kind: "rate_limited",
        message: "Market data provider is temporarily rate limited. Please try again shortly.",
      };
    }
    if (status === 503 || status === 504) {
      return {
        kind: "unavailable",
        message: "Market data provider is temporarily unavailable. Please try again shortly.",
      };
    }
    if (status >= 500) {
      return { kind: "server", message: "Market data could not be loaded. Please retry." };
    }
    // 4xx: the backend's error body is already a clean, human-readable sentence.
    return { kind: "client", message: error.message || fallback };
  }

  if (error instanceof Error && error.message) {
    return { kind: "unknown", message: error.message };
  }
  return { kind: "unknown", message: fallback };
}

export function toErrorMessage(error: unknown, fallback: string): string {
  return classifyError(error, fallback).message;
}
