import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../context/ThemeContext";
import { accuracy, config, decisionEvaluation, paged } from "../test-fixtures/backtesting";
import { signInWithReadyStores, signOut } from "../test-fixtures/userFeatures";
import { backtestingApi } from "../services/api/backtesting.api";
import { AppRoutes } from "./AppRoutes";

vi.mock("../services/api/backtesting.api", () => ({
  backtestingApi: {
    config: vi.fn(), accuracy: vi.fn(), refreshOutcomes: vi.fn(), refreshStatus: vi.fn(), decisions: vi.fn(),
    createRun: vi.fn(), listRuns: vi.fn(), getRun: vi.fn(), runTrades: vi.fn(),
  },
  splitModelVersion: vi.fn(),
}));
vi.mock("../services/api/watchlist.api", () => ({ watchlistApi: { list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, limit: 250, pages: 0 }), add: vi.fn(), remove: vi.fn(), status: vi.fn() } }));
vi.mock("../services/api/settings.api", () => ({ settingsApi: { get: vi.fn().mockResolvedValue({ theme: null, notifications: { price_alerts: true } }), update: vi.fn() } }));

const api = vi.mocked(backtestingApi);

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ThemeProvider>
        <AppRoutes />
      </ThemeProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  signOut();
  api.config.mockResolvedValue(config());
  api.accuracy.mockResolvedValue(accuracy());
  api.decisions.mockResolvedValue(decisionEvaluation());
  api.listRuns.mockResolvedValue(paged([]) as never);
});

describe("/backtesting route", () => {
  it("redirects an unauthenticated visitor to Login without calling the API", () => {
    renderRoute("/backtesting");
    expect(screen.getByRole("heading", { name: /log ?in|sign ?in|welcome/i })).toBeInTheDocument();
    expect(api.accuracy).not.toHaveBeenCalled();
  });

  it("renders for a signed-in user, with exactly one navigation entry", async () => {
    signInWithReadyStores();
    renderRoute("/backtesting");
    expect(await screen.findByRole("heading", { level: 1, name: "Backtesting & Model Accuracy" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Main" });
    const links = within(nav).getAllByRole("link", { name: "Backtesting & Accuracy" });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/backtesting");
    expect(links[0]).toHaveAttribute("aria-current", "page");
  });
});
