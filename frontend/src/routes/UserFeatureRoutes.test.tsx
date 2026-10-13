import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../context/ThemeContext";
import { signInWithReadyStores, signOut } from "../test-fixtures/userFeatures";
import { AppRoutes } from "./AppRoutes";

vi.mock("../services/api/watchlist.api", () => ({ watchlistApi: { list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, limit: 250, pages: 0 }), add: vi.fn(), remove: vi.fn(), status: vi.fn() } }));
vi.mock("../services/api/portfolio.api", () => ({ portfolioApi: { get: vi.fn().mockResolvedValue({ currency: "USD", holdings: [], summary: { total_current_value: 0, total_invested: 0, priced_invested: 0, total_unrealized_pnl: null, total_unrealized_pnl_pct: null, holdings_count: 0, unpriced_count: 0, is_partial: false } }), add: vi.fn(), update: vi.fn(), remove: vi.fn(), transactions: vi.fn() } }));
vi.mock("../services/api/history.api", () => ({ historyApi: { list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, limit: 20, pages: 0 }), record: vi.fn(), remove: vi.fn() } }));
vi.mock("../services/api/alerts.api", () => ({ alertsApi: { list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, limit: 100, pages: 0 }), create: vi.fn(), update: vi.fn(), remove: vi.fn(), check: vi.fn() } }));
vi.mock("../services/api/profile.api", () => ({ profileApi: { get: vi.fn().mockResolvedValue({ id: "u1", name: "Test User", email: "test@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" }), updateName: vi.fn(), changePassword: vi.fn() } }));
vi.mock("../services/api/settings.api", () => ({ settingsApi: { get: vi.fn().mockResolvedValue({ theme: null, notifications: { price_alerts: true } }), update: vi.fn() } }));

const PATHS = ["/watchlist", "/portfolio", "/history", "/alerts", "/profile", "/settings"];

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ThemeProvider>
        <AppRoutes />
      </ThemeProvider>
    </MemoryRouter>
  );
}

beforeEach(() => signOut());

describe("Phase 16 routes", () => {
  it.each(PATHS)("%s redirects an unauthenticated visitor to Login", (path) => {
    renderRoute(path);
    expect(screen.getByRole("heading", { name: /log ?in|sign ?in|welcome/i })).toBeInTheDocument();
  });

  it.each([
    ["/watchlist", "Watchlist"],
    ["/portfolio", "Portfolio"],
    ["/history", "Analysis History"],
    ["/alerts", "Alerts"],
    ["/profile", "Profile"],
    ["/settings", "Settings"],
  ])("%s renders for a signed-in user", async (path, heading) => {
    signInWithReadyStores();
    renderRoute(path);
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });

  it("the main navigation links to every user feature", () => {
    signInWithReadyStores();
    renderRoute("/settings");
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const label of ["Dashboard", "Markets", "Watchlist", "Portfolio", "History", "Alerts"]) {
      expect(nav).toHaveTextContent(label);
    }
    // Profile and Settings live in the account menu and (Settings) the sidebar footer.
    expect(screen.getAllByRole("link", { name: "Settings" })[0]).toHaveAttribute("href", "/settings");
  });
});
