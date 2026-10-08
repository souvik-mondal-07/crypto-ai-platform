import { create } from "zustand";

import { authApi } from "../services/api/auth.api";
import { AUTH_SESSION_INVALID_EVENT } from "../services/api/client";
import { getToken, removeToken, setToken } from "../utils/authStorage";
import type { User } from "../types/auth";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  /** True while the app is checking a stored token on startup, or while login/register is in flight. */
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, confirmPassword: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Called once on app startup: if a token is stored, verify it against /auth/me before trusting it. */
  initializeAuth: () => Promise<void>;
  clearError: () => void;
}

/**
 * The ONLY place the authenticated user lives in the frontend.
 * `user` always comes from the backend's /auth/me response — never a
 * hard-coded name, a value derived from the login form input, or any
 * other local guess. See docs/authentication.md for why this
 * single-source-of-truth rule matters.
 */
export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const { token } = await authApi.login({ email, password });
      setToken(token.access_token);

      // Always re-fetch the actual user from /auth/me rather than
      // trusting anything derived from the login form or the token
      // payload — /auth/me is the single source of truth.
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false, error: null });
    } catch (error) {
      removeToken();
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: error instanceof Error ? error.message : "Login failed.",
      });
      throw error;
    }
  },

  register: async (name: string, email: string, password: string, confirmPassword: string) => {
    set({ isLoading: true, error: null });
    try {
      // V1 behavior (documented in docs/authentication.md): registration
      // does NOT log the user in automatically. It only creates the
      // account; the caller is expected to redirect to /login afterward.
      await authApi.register({ name, email, password, confirm_password: confirmPassword });
      set({ isLoading: false, error: null });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : "Registration failed.",
      });
      throw error;
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch {
      // Logout is a client-side state clear regardless of whether the
      // network call succeeds — see docs/authentication.md for why a
      // stateless JWT can't be server-invalidated in V1.
    }
    removeToken();
    set({ user: null, isAuthenticated: false, isLoading: false, error: null });
  },

  initializeAuth: async () => {
    const token = getToken();
    if (!token) {
      set({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }

    set({ isLoading: true });
    try {
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false, error: null });
    } catch {
      // Token exists but is invalid/expired — clear it rather than
      // showing a stale or fake authenticated state.
      removeToken();
      set({ user: null, isAuthenticated: false, isLoading: false, error: null });
    }
  },

  clearError: () => set({ error: null }),
}));

// A 401 on any authenticated request (not a login/register attempt —
// see client.ts) means the session is no longer valid. Clear state
// the same way logout does, without needing client.ts to import this
// store directly (which would create a circular dependency).
if (typeof window !== "undefined") {
  window.addEventListener(AUTH_SESSION_INVALID_EVENT, () => {
    useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
  });
}
