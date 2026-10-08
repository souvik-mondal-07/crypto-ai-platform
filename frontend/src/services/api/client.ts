import axios, { AxiosError } from "axios";

import { apiConfig } from "../../config/api.config";
import { ApiError, type ApiErrorBody } from "../../types/apiError";
import { getToken, removeToken } from "../../utils/authStorage";

/**
 * Shared Axios instance for all backend requests.
 * Future feature services (market, prediction, etc.) should import this
 * client rather than creating their own axios instances.
 */
export const apiClient = axios.create({
  baseURL: apiConfig.baseURL,
  timeout: apiConfig.timeout,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach the stored token to every request automatically — no
// service/component should ever set this header itself.
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Requests where a 401 means "these specific credentials were wrong"
// (a normal, expected form-validation-style error) rather than "the
// session/token is no longer valid" — these must NOT trigger the
// clear-and-redirect behavior below, or a failed login attempt would
// wipe state and bounce the user away from the very form showing them
// the error.
const CREDENTIAL_CHECK_ENDPOINTS = [apiConfig.endpoints.authLogin, apiConfig.endpoints.authRegister];

/**
 * Fired when a 401 indicates the current session is no longer valid
 * (expired/invalid token on an authenticated request) — NOT fired for
 * a login-form rejection. `authStore` listens for this to clear its
 * state; kept as an event rather than a direct import to avoid a
 * circular dependency between this client and the store that uses it.
 */
export const AUTH_SESSION_INVALID_EVENT = "auth:session-invalid";

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    const requestUrl = error.config?.url ?? "";
    const isCredentialCheck = CREDENTIAL_CHECK_ENDPOINTS.some((endpoint) => requestUrl.includes(endpoint));

    if (error.response?.status === 401 && !isCredentialCheck) {
      removeToken();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent(AUTH_SESSION_INVALID_EVENT));
      }
    }

    // Centralized, clean error normalization. Components should never
    // need to inspect raw Axios error internals. The backend always
    // returns { error: { code, message } } on failure (see
    // backend/app/core/exceptions.py) — prefer that human-readable
    // message over the raw HTTP status text when it's present.
    const message =
      error.response?.data?.error?.message ||
      error.response?.statusText ||
      error.message ||
      "An unexpected network error occurred.";

    return Promise.reject(new ApiError(message, error.response?.status, error.response?.data?.error?.code));
  }
);
