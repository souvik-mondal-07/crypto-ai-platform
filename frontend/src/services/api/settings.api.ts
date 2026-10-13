import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { UserSettings, UserSettingsUpdate } from "../../types/userFeatures";

export const settingsApi = {
  async get(): Promise<UserSettings> {
    const { data } = await apiClient.get<UserSettings>(apiConfig.endpoints.settings);
    return data;
  },
  async update(payload: UserSettingsUpdate): Promise<UserSettings> {
    const { data } = await apiClient.put<UserSettings>(apiConfig.endpoints.settings, payload);
    return data;
  },
};
