import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type {
  AlertCheckResult,
  AlertCreate,
  AlertList,
  AlertStatus,
  AlertUpdate,
  PriceAlert,
} from "../../types/userFeatures";

export const alertsApi = {
  async list(page = 1, limit = 100, status?: AlertStatus): Promise<AlertList> {
    const { data } = await apiClient.get<AlertList>(apiConfig.endpoints.alerts, {
      params: { page, limit, ...(status ? { status } : {}) },
    });
    return data;
  },
  async create(payload: AlertCreate): Promise<PriceAlert> {
    const { data } = await apiClient.post<PriceAlert>(apiConfig.endpoints.alerts, payload);
    return data;
  },
  async update(id: string, payload: AlertUpdate): Promise<PriceAlert> {
    const { data } = await apiClient.put<PriceAlert>(apiConfig.endpoints.alert(id), payload);
    return data;
  },
  async remove(id: string): Promise<void> {
    await apiClient.delete(apiConfig.endpoints.alert(id));
  },
  /** Runs one real evaluation of MY active alerts against stored market data. */
  async check(): Promise<AlertCheckResult> {
    const { data } = await apiClient.post<AlertCheckResult>(apiConfig.endpoints.alertsCheck);
    return data;
  },
};
