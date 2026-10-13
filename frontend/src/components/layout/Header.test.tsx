import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
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

const signIn = () =>
  useAuthStore.setState({
    isAuthenticated: true,
    user: { id: "1", name: "Actual Registered Name", email: "x@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
  });

function renderHeader(props: Parameters<typeof Header>[0] = {}) {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Header {...props} />
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
    signIn();
    renderHeader();
    expect(screen.getByText("Actual Registered Name")).toBeInTheDocument();
  });

  it("clears authentication state on logout, from the account menu", async () => {
    signIn();
    mockedAuthApi.logout.mockResolvedValue({ message: "Logged out successfully" });

    const user = userEvent.setup();
    renderHeader();

    // Logout is not a permanent bar item: it lives in the account menu.
    expect(screen.queryByRole("menuitem", { name: /logout/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /account/i }));
    await user.click(screen.getByRole("menuitem", { name: /logout/i }));

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });

  describe("account menu", () => {
    it("is closed by default and offers Profile, Settings and Logout when opened", async () => {
      signIn();
      const user = userEvent.setup();
      renderHeader();
      const trigger = screen.getByRole("button", { name: /account/i });
      expect(trigger).toHaveAttribute("aria-expanded", "false");
      expect(screen.queryByRole("menu")).not.toBeInTheDocument();

      await user.click(trigger);
      const menu = screen.getByRole("menu", { name: "Account menu" });
      expect(trigger).toHaveAttribute("aria-expanded", "true");
      expect(within(menu).getByRole("menuitem", { name: "Profile" })).toHaveAttribute("href", "/profile");
      expect(within(menu).getByRole("menuitem", { name: "Settings" })).toHaveAttribute("href", "/settings");
      expect(within(menu).getByRole("menuitem", { name: "Logout" })).toBeInTheDocument();
    });

    it("closes with Escape", async () => {
      signIn();
      const user = userEvent.setup();
      renderHeader();
      await user.click(screen.getByRole("button", { name: /account/i }));
      await user.keyboard("{Escape}");
      expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    });

    it("shows the user's role as the membership label, not an invented plan", () => {
      signIn();
      renderHeader();
      expect(screen.getByText("User")).toBeInTheDocument();
      expect(screen.queryByText(/premium/i)).not.toBeInTheDocument();
    });
  });

  describe("layout controls", () => {
    it("opens the sidebar drawer from the menu button when a handler is provided", async () => {
      signIn();
      const onOpenMenu = vi.fn();
      const user = userEvent.setup();
      renderHeader({ onOpenMenu });
      const button = screen.getByRole("button", { name: "Open menu" });
      expect(button).toHaveAttribute("aria-expanded", "false");
      await user.click(button);
      expect(onOpenMenu).toHaveBeenCalledTimes(1);
    });

    it("has no navigation of its own (the sidebar owns it) but keeps the search in its own flexible slot", () => {
      signIn();
      renderHeader();
      expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
      expect(screen.getByRole("search")).toBeInTheDocument();
    });

    it("links the bell to Alerts and badges it only when there are active alerts", () => {
      signIn();
      const { unmount } = renderHeader();
      expect(screen.getByRole("link", { name: "Alert notifications" })).toHaveAttribute("href", "/alerts");
      unmount();
      renderHeader({ alertCount: 3 });
      expect(screen.getByRole("link", { name: "Alert notifications (3 active)" })).toHaveAttribute("href", "/alerts");
    });
  });
});
