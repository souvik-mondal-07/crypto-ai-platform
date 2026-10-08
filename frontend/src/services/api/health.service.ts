import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { HealthResponse } from "../../types/health.types";

/**
 * Calls the backend health endpoint.
 * Throws (via the apiClient interceptor) on any network/HTTP failure —
 * callers are expected to catch and translate into UI state.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>(apiConfig.endpoints.health);
  return data;
}
