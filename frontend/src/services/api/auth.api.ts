import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type {
  AuthResponse,
  LoginRequest,
  LogoutResponse,
  RegisterRequest,
  RegisterResponse,
  User,
} from "../../types/auth";

/**
 * All authentication HTTP calls live here. Components must never call
 * axios directly — always go through these functions.
 */
export const authApi = {
  async register(payload: RegisterRequest): Promise<RegisterResponse> {
    const { data } = await apiClient.post<RegisterResponse>(apiConfig.endpoints.authRegister, payload);
    return data;
  },

  async login(payload: LoginRequest): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>(apiConfig.endpoints.authLogin, payload);
    return data;
  },

  /** The single source of truth for "who is currently authenticated" — always calls the backend, never returns a cached/local guess. */
  async me(): Promise<User> {
    const { data } = await apiClient.get<User>(apiConfig.endpoints.authMe);
    return data;
  },

  async logout(): Promise<LogoutResponse> {
    const { data } = await apiClient.post<LogoutResponse>(apiConfig.endpoints.authLogout);
    return data;
  },
};
