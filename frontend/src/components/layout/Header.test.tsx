import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { Header } from "./Header";
import { useAuthStore } from "../../store/authStore";
import { ThemeProvider } from "../../context/ThemeContext";
import { authApi } from "../../services/api/auth.api";

vi.mock("../../services/api/auth.api", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}));

const mockedAuthApi = vi.mocked(authApi);

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
});

function renderHeader() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Header />
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe("Header", () => {
  it("shows a Log in link when unauthenticated, never a fake user name", () => {
    renderHeader();
    expect(screen.getByRole("link", { name: /log in/i })).toBeInTheDocument();
    expect(screen.queryByText("Demo User")).not.toBeInTheDocument();
  });

  it("shows the actual authenticated user's name when logged in", () => {
    useAuthStore.setState({
      isAuthenticated: true,
      user: { id: "1", name: "Actual Registered Name", email: "x@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
    });
    renderHeader();
    expect(screen.getByText("Actual Registered Name")).toBeInTheDocument();
  });

  it("clears authentication state on logout", async () => {
    useAuthStore.setState({
      isAuthenticated: true,
      user: { id: "1", name: "Actual Registered Name", email: "x@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
    });
    mockedAuthApi.logout.mockResolvedValue({ message: "Logged out successfully" });

    const user = userEvent.setup();
    renderHeader();

    await user.click(screen.getByRole("button", { name: /logout/i }));

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });
});
