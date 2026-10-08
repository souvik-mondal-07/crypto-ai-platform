export interface HealthResponse {
  status: string;
  service: string;
}

export type BackendStatus = "checking" | "online" | "offline";
