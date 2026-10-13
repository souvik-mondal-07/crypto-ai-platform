import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../context/ThemeContext";
import { usePortfolioStore } from "../store/portfolioStore";
import { useAuthStore } from "../store/authStore";
import { DEFAULT_SETTINGS, useSettingsStore } from "../store/settingsStore";
import { useWatchlistStore } from "../store/watchlistStore";
import type { AlertList, Holding, HistoryEntry, PriceAlert, Portfolio, WatchlistItem } from "../types/userFeatures";

export const USER = { id: "u1", name: "Test User", email: "test@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" };
export const COIN_BTC = "a".repeat(24);
export const COIN_ETH = "b".repeat(24);

/** Signed-in user with already-loaded (empty) server stores, so AppShell's sync does no network work. */
export function signInWithReadyStores(): void {
  useAuthStore.setState({ user: USER, isAuthenticated: true, isLoading: false, error: null });
  useWatchlistStore.setState({ userId: USER.id, ids: [], status: "ready", error: null, notice: null, pending: [] });
  useSettingsStore.setState({ userId: USER.id, settings: DEFAULT_SETTINGS, status: "ready", error: null, saving: false, saveError: null });
  usePortfolioStore.setState({ userId: null, portfolio: null, status: "idle", error: null, saving: false, actionError: null });
}

export function signOut(): void {
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
}

export function renderAt(element: ReactElement, target: string | { path: string; state?: unknown }) {
  const path = typeof target === "string" ? target : target.path;
  const entry = typeof target === "string" ? target : { pathname: target.path, state: target.state };
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <ThemeProvider>
        <Routes>
          <Route path={path} element={element} />
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/coins/:coinId" element={<div>Coin Details Page</div>} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

export const holding = (over: Partial<Holding> = {}): Holding => ({
  coin_id: COIN_BTC, name: "Bitcoin", symbol: "btc", logo_url: null, quantity: 2, average_buy_price: 50, invested_value: 100,
  has_price: true, current_price: 100, current_value: 200, unrealized_pnl: 100, unrealized_pnl_pct: 100, percent_change_24h: 2.5,
  allocation_pct: 100, price_last_updated: "2026-10-09T00:00:00Z", price_is_stale: false, notes: null,
  created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z", ...over,
});

export const portfolio = (holdings: Holding[] = [holding()], over: Partial<Portfolio["summary"]> = {}): Portfolio => ({
  currency: "USD",
  holdings,
  summary: {
    total_current_value: 200, total_invested: 100, priced_invested: 100, total_unrealized_pnl: 100, total_unrealized_pnl_pct: 100,
    holdings_count: holdings.length, unpriced_count: 0, is_partial: false, ...over,
  },
});

export const watchItem = (over: Partial<WatchlistItem> = {}): WatchlistItem => ({
  coin_id: COIN_BTC, name: "Bitcoin", symbol: "btc", logo_url: null, market_cap_rank: 1, price_usd: 100, percent_change_24h: 2.5,
  market_cap_usd: 1e9, volume_24h_usd: 1e6, last_updated: "2026-10-09T00:00:00Z", is_stale: false, added_at: "2026-10-01T00:00:00Z", ...over,
});

export const historyEntry = (over: Partial<HistoryEntry> = {}): HistoryEntry => ({
  id: "h".repeat(24), coin_id: COIN_BTC, coin_name: "Bitcoin", symbol: "btc", analysis_type: "risk_decision", status: "COMPLETED",
  decision: "BUY", risk_level: "LOW", risk_score: 30, summary: "Decision BUY, LOW risk", created_at: "2026-10-09T00:00:00Z", ...over,
});

export const alert = (over: Partial<PriceAlert> = {}): PriceAlert => ({
  id: "c".repeat(24), coin_id: COIN_BTC, name: "Bitcoin", symbol: "btc", logo_url: null, alert_type: "price", condition: "ABOVE",
  target_price: 120000, status: "ACTIVE", current_price: 100000, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  triggered_at: null, triggered_price: null, expires_at: null, last_checked_at: null, ...over,
});

export const alertList = (items: PriceAlert[]): AlertList => ({ items, total: items.length, page: 1, limit: 100, pages: items.length ? 1 : 0 });
