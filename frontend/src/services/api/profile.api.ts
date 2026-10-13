import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { ChangePasswordPayload, Profile } from "../../types/userFeatures";

export const profileApi = {
  async get(): Promise<Profile> {
    const { data } = await apiClient.get<Profile>(apiConfig.endpoints.profile);
    return data;
  },
  async updateName(name: string): Promise<Profile> {
    const { data } = await apiClient.put<Profile>(apiConfig.endpoints.profile, { name });
    return data;
  },
  async changePassword(payload: ChangePasswordPayload): Promise<void> {
    await apiClient.post(apiConfig.endpoints.profilePassword, payload);
  },
};
