import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "./authStore";
import { authApi } from "../services/api/auth.api";
import { AUTH_SESSION_INVALID_EVENT } from "../services/api/client";
import * as authStorage from "../utils/authStorage";

vi.mock("../services/api/auth.api", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}));

const mockedAuthApi = vi.mocked(authApi);

function resetStore() {
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
}

beforeEach(() => {
  vi.clearAllMocks();
  authStorage.removeToken();
  resetStore();
});

describe("authStore.login", () => {
  it("stores the token and the ACTUAL user returned by /auth/me, not a sample value", async () => {
    mockedAuthApi.login.mockResolvedValue({
      user: { id: "1", name: "should-be-ignored", email: "x@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
      token: { access_token: "real-token-abc", token_type: "bearer", expires_in_minutes: 60 },
    });
    mockedAuthApi.me.mockResolvedValue({
      id: "1",
      name: "Actual Registered Name",
      email: "actual@example.com",
      role: "user",
      created_at: "2026-01-01T00:00:00Z",
    });

    await useAuthStore.getState().login("actual@example.com", "password123");

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user?.name).toBe("Actual Registered Name");
    expect(state.user?.email).toBe("actual@example.com");
    expect(authStorage.getToken()).toBe("real-token-abc");
    // /auth/me is always called — the user is never assumed from the login response alone.
    expect(mockedAuthApi.me).toHaveBeenCalledTimes(1);
  });

  it("never displays a hard-coded sample name on failure", async () => {
    mockedAuthApi.login.mockRejectedValue(new Error("Invalid email or password."));

    await expect(useAuthStore.getState().login("wrong@example.com", "bad")).rejects.toThrow();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.error).toBe("Invalid email or password.");
  });

  it("clears any stored token if login fails", async () => {
    authStorage.setToken("stale-token");
    mockedAuthApi.login.mockRejectedValue(new Error("Invalid email or password."));

    await expect(useAuthStore.getState().login("x@example.com", "bad")).rejects.toThrow();

    expect(authStorage.getToken()).toBeNull();
  });
});

describe("authStore.register", () => {
  it("does NOT authenticate the user automatically after registration (V1 behavior)", async () => {
    mockedAuthApi.register.mockResolvedValue({
      user: { id: "1", name: "New User", email: "new@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
      message: "Registration successful",
    });

    await useAuthStore.getState().register("New User", "new@example.com", "password123", "password123");

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(mockedAuthApi.me).not.toHaveBeenCalled();
  });
});

describe("authStore.logout", () => {
  it("clears user, token, and isAuthenticated even if the network call fails", async () => {
    useAuthStore.setState({
      user: { id: "1", name: "Someone", email: "s@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });
    authStorage.setToken("some-token");
    mockedAuthApi.logout.mockRejectedValue(new Error("network down"));

    await useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(authStorage.getToken()).toBeNull();
  });
});

describe("authStore.initializeAuth", () => {
  it("restores the actual user when a stored token is still valid", async () => {
    authStorage.setToken("valid-token");
    mockedAuthApi.me.mockResolvedValue({
      id: "1", name: "Restored User", email: "restored@example.com", role: "user", created_at: "2026-01-01T00:00:00Z",
    });

    await useAuthStore.getState().initializeAuth();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user?.name).toBe("Restored User");
    expect(state.isLoading).toBe(false);
  });

  it("clears state (no fake user) when the stored token is invalid", async () => {
    authStorage.setToken("expired-token");
    mockedAuthApi.me.mockRejectedValue(new Error("Session expired"));

    await useAuthStore.getState().initializeAuth();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(authStorage.getToken()).toBeNull();
  });

  it("skips the /auth/me call entirely when no token is stored", async () => {
    await useAuthStore.getState().initializeAuth();

    expect(mockedAuthApi.me).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});

describe("session-invalid event (401 handling)", () => {
  it("clears authentication state when the client dispatches AUTH_SESSION_INVALID_EVENT", () => {
    useAuthStore.setState({
      user: { id: "1", name: "Someone", email: "s@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    window.dispatchEvent(new CustomEvent(AUTH_SESSION_INVALID_EVENT));

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });
});
