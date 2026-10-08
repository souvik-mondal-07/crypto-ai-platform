import { ApiError } from "../types/apiError";

export type DecisionErrorKind = "network" | "timeout" | "rate_limited" | "unavailable" | "not_found" | "invalid" | "server" | "unknown";

/** User-safe wording for failed decision requests (never a stack trace). */
export function describeDecisionError(error: unknown): { kind: DecisionErrorKind; message: string } {
  if (error instanceof ApiError) {
    const { status, code } = error;
    if (status === undefined) {
      return /timeout|timed out/i.test(error.message)
        ? { kind: "timeout", message: "The risk and decision request took too long. Please retry." }
        : { kind: "network", message: "Unable to reach the server. Check your connection and retry." };
    }
    if (status === 429) return { kind: "rate_limited", message: "The analysis is temporarily rate limited. Please try again shortly." };
    if (status === 503 || status === 504) {
      return { kind: "unavailable", message: "The data needed for the risk and decision analysis is temporarily unavailable. Please try again shortly." };
    }
    if (status >= 500) return { kind: "server", message: "The risk and decision analysis could not be loaded. Please retry." };
    if (status === 404) {
      return code === "COIN_NOT_FOUND"
        ? { kind: "not_found", message: "This cryptocurrency was not found." }
        : { kind: "not_found", message: error.message || "Not found." };
    }
    return { kind: "invalid", message: error.message || "The risk and decision request was not valid." };
  }
  if (error instanceof Error && error.message) return { kind: "unknown", message: error.message };
  return { kind: "unknown", message: "The risk and decision analysis could not be loaded. Please retry." };
}
