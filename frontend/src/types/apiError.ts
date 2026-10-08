export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}

/**
 * The Error every failed API request rejects with (see
 * services/api/client.ts). It is still a plain `Error` with the same
 * human-readable `message` as before — existing callers are unaffected —
 * but additionally carries the HTTP status and the backend's machine
 * code (e.g. "FUNDAMENTALS_NOT_AVAILABLE"), so callers can tell
 * "no data exists" from "the request failed" without parsing message text.
 */
export class ApiError extends Error {
  readonly status: number | undefined;
  readonly code: string | undefined;

  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}
