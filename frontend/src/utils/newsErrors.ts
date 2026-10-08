import { ApiError } from "../types/apiError";

export type NewsErrorKind = "network" | "timeout" | "rate_limited" | "unavailable" | "not_found" | "invalid" | "server" | "unknown";

/**
 * User-safe wording for news/sentiment request failures. (utils/apiErrors.ts
 * words its 429/503 messages for *market data*, which would be wrong here.)
 */
export function describeNewsError(error: unknown): { kind: NewsErrorKind; message: string } {
  if (error instanceof ApiError) {
    const { status, code } = error;
    if (status === undefined) {
      return /timeout|timed out/i.test(error.message)
        ? { kind: "timeout", message: "The news request took too long. Please retry." }
        : { kind: "network", message: "Unable to reach the server. Check your connection and retry." };
    }
    if (status === 429) return { kind: "rate_limited", message: "News is temporarily rate limited. Please try again shortly." };
    if (status === 503 || status === 504) {
      return { kind: "unavailable", message: "News is temporarily unavailable. Please try again shortly." };
    }
    if (status >= 500) return { kind: "server", message: "News could not be loaded. Please retry." };
    if (status === 404) {
      return code === "COIN_NOT_FOUND"
        ? { kind: "not_found", message: "This cryptocurrency was not found." }
        : { kind: "not_found", message: error.message || "Not found." };
    }
    return { kind: "invalid", message: error.message || "The news request was not valid." };
  }
  if (error instanceof Error && error.message) return { kind: "unknown", message: error.message };
  return { kind: "unknown", message: "News could not be loaded. Please retry." };
}

/** Plain-language reason for the backend's `last_sync_error_code`. */
export function describeSyncError(code: string | null): string | null {
  switch (code) {
    case null:
    case undefined:
      return null;
    case "PROVIDER_RATE_LIMITED":
      return "the news provider rate-limited the last refresh";
    case "PROVIDER_TIMEOUT":
      return "the news provider did not respond in time";
    case "PROVIDER_UNAVAILABLE":
      return "the news provider is unreachable";
    case "DATABASE_UNAVAILABLE":
      return "the database was unavailable";
    default:
      return "the last refresh failed";
  }
}
