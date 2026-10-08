import { env } from "../config/environment";
import { ApiError } from "../types/apiError";

export type AiErrorKind =
  | "unavailable"
  | "rate_limited"
  | "cooldown"
  | "timeout"
  | "insufficient_data"
  | "network"
  | "not_found"
  | "no_analysis"
  | "server"
  | "unknown";

export interface AiErrorInfo {
  kind: AiErrorKind;
  /** User-safe wording (never a stack trace or a provider message). */
  message: string;
}

export const AI_UNAVAILABLE_MESSAGE = "AI analysis is temporarily unavailable.";

/** Backend codes meaning "the AI service itself cannot be used right now" (config, credentials, provider, output). */
const UNAVAILABLE_CODES = new Set([
  "AI_NOT_CONFIGURED",
  "AI_AUTH_FAILED",
  "AI_UNAVAILABLE",
  "AI_INVALID_RESPONSE",
  "AI_REQUEST_REJECTED",
]);

/** True for a 404 meaning "no explanation has been generated for this coin yet" (not a failure). */
export function isNoAnalysisYet(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404 && error.code === "AI_ANALYSIS_NOT_FOUND";
}

export function describeAiError(error: unknown): AiErrorInfo {
  if (error instanceof ApiError) {
    const { status, code } = error;
    if (status === undefined) {
      return /timeout|timed out/i.test(error.message)
        ? { kind: "timeout", message: "The AI analysis took too long. Please retry." }
        : { kind: "network", message: "Unable to reach the server. Check your connection and retry." };
    }
    if (code && UNAVAILABLE_CODES.has(code)) return { kind: "unavailable", message: AI_UNAVAILABLE_MESSAGE };
    if (code === "AI_TIMEOUT" || status === 504) return { kind: "timeout", message: "The AI analysis took too long. Please retry." };
    if (code === "AI_RATE_LIMITED") {
      return { kind: "rate_limited", message: "AI analysis is rate limited right now. Please try again shortly." };
    }
    if (code === "AI_ANALYSIS_COOLDOWN") {
      return { kind: "cooldown", message: error.message || "An analysis was generated moments ago. Please wait a moment." };
    }
    if (code === "AI_INSUFFICIENT_DATA") {
      return { kind: "insufficient_data", message: error.message || "There is not enough platform data to explain this coin yet." };
    }
    if (status === 429) return { kind: "rate_limited", message: "AI analysis is rate limited right now. Please try again shortly." };
    if (status === 404) {
      return code === "AI_ANALYSIS_NOT_FOUND"
        ? { kind: "no_analysis", message: "No AI analysis has been generated for this coin yet." }
        : { kind: "not_found", message: "This cryptocurrency was not found." };
    }
    if (status === 502 || status === 503) return { kind: "unavailable", message: AI_UNAVAILABLE_MESSAGE };
    if (status >= 500) return { kind: "server", message: "The AI analysis could not be loaded. Please retry." };
    return { kind: "unknown", message: error.message || "The AI analysis request was not valid." };
  }
  return { kind: "unknown", message: "The AI analysis could not be loaded. Please retry." };
}

/**
 * Development-only diagnostics. The UI deliberately shows a short, safe message; this puts the real
 * cause (HTTP status, backend code, or the underlying JavaScript error) in the browser console so a
 * failing AI section is never a mystery. Never logs response bodies, tokens or any key.
 */
export function logAiError(context: string, error: unknown): void {
  if (!env.isDevelopment) return;
  if (error instanceof ApiError) {
    console.error(`[AI analysis] ${context} failed`, { status: error.status, code: error.code, message: error.message });
  } else {
    console.error(`[AI analysis] ${context} failed with a non-API error`, error);
  }
}
