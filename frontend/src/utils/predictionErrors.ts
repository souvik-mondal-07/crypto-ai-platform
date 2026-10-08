import { ApiError } from "../types/apiError";

export type PredictionErrorKind =
  | "network" | "timeout" | "rate_limited" | "unavailable" | "not_found" | "engine_unavailable" | "invalid" | "server" | "unknown";

/** User-safe wording for failed prediction requests (never a stack trace). */
export function describePredictionError(error: unknown): { kind: PredictionErrorKind; message: string } {
  if (error instanceof ApiError) {
    const { status, code } = error;
    if (status === undefined) {
      return /timeout|timed out/i.test(error.message)
        ? { kind: "timeout", message: "The prediction request took too long. Please retry." }
        : { kind: "network", message: "Unable to reach the server. Check your connection and retry." };
    }
    if (status === 429) return { kind: "rate_limited", message: "Predictions are temporarily rate limited. Please try again shortly." };
    if (code === "PREDICTION_ENGINE_UNAVAILABLE") {
      return { kind: "engine_unavailable", message: "The prediction engine is not available on the server right now." };
    }
    if (status === 503 || status === 504) {
      return { kind: "unavailable", message: "Market data needed for predictions is temporarily unavailable. Please try again shortly." };
    }
    if (status >= 500) return { kind: "server", message: "Predictions could not be loaded. Please retry." };
    if (status === 404) {
      return code === "COIN_NOT_FOUND"
        ? { kind: "not_found", message: "This cryptocurrency was not found." }
        : { kind: "not_found", message: error.message || "Not found." };
    }
    return { kind: "invalid", message: error.message || "The prediction request was not valid." };
  }
  if (error instanceof Error && error.message) return { kind: "unknown", message: error.message };
  return { kind: "unknown", message: "Predictions could not be loaded. Please retry." };
}
