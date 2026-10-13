import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { alertsApi } from "../services/api/alerts.api";
import { historyApi } from "../services/api/history.api";
import { portfolioApi } from "../services/api/portfolio.api";
import { profileApi } from "../services/api/profile.api";
import { settingsApi } from "../services/api/settings.api";
import { watchlistApi } from "../services/api/watchlist.api";
import { ApiError } from "../types/apiError";
import { useWatchlistStore } from "../store/watchlistStore";
import {
  COIN_BTC, USER, alert, alertList, historyEntry, holding, portfolio, renderAt, signInWithReadyStores, watchItem,
} from "../test-fixtures/userFeatures";
import { Alerts } from "./Alerts";
import { History } from "./History/History";
import { Portfolio } from "./Portfolio/Portfolio";
import { Profile } from "./Profile";
import { Settings } from "./Settings";
import { Watchlist } from "./Watchlist";

vi.mock("../services/api/watchlist.api", () => ({ watchlistApi: { list: vi.fn(), add: vi.fn(), remove: vi.fn(), status: vi.fn() } }));
vi.mock("../services/api/portfolio.api", () => ({ portfolioApi: { get: vi.fn(), add: vi.fn(), update: vi.fn(), remove: vi.fn(), transactions: vi.fn() } }));
vi.mock("../services/api/history.api", () => ({ historyApi: { list: vi.fn(), record: vi.fn(), remove: vi.fn() } }));
vi.mock("../services/api/alerts.api", () => ({ alertsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), check: vi.fn() } }));
vi.mock("../services/api/profile.api", () => ({ profileApi: { get: vi.fn(), updateName: vi.fn(), changePassword: vi.fn() } }));
vi.mock("../services/api/settings.api", () => ({ settingsApi: { get: vi.fn(), update: vi.fn() } }));
vi.mock("../services/api/coins.api", () => ({
  fetchCoins: vi.fn(),
  fetchCoinById: vi.fn(),
  searchCoins: vi.fn().mockResolvedValue({ items: [], query: "", count: 0 }),
}));

const watchlistMock = vi.mocked(watchlistApi);
const portfolioMock = vi.mocked(portfolioApi);
const historyMock = vi.mocked(historyApi);
const alertsMock = vi.mocked(alertsApi);
const profileMock = vi.mocked(profileApi);
const settingsMock = vi.mocked(settingsApi);

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, limit: 20, pages: items.length ? 1 : 0 });

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  signInWithReadyStores();
});

describe("Watchlist page", () => {
  it("shows a loading state, then the user's coins with real market fields", async () => {
    useWatchlistStore.setState({ ids: [COIN_BTC] });
    watchlistMock.list.mockResolvedValue(page([watchItem()]) as never);
    renderAt(<Watchlist />, "/watchlist");
    expect(screen.getByText(/loading your watchlist/i)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /bitcoin/i })).toHaveAttribute("href", `/coins/${COIN_BTC}`);
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("$100.00")).toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    watchlistMock.list.mockResolvedValue(page([]) as never);
    renderAt(<Watchlist />, "/watchlist");
    expect(await screen.findByText(/your watchlist is empty\. add coins from the markets or coin details page/i)).toBeInTheDocument();
  });

  it("shows an error with Retry — never an endless spinner", async () => {
    watchlistMock.list.mockRejectedValueOnce(new ApiError("boom", 500));
    renderAt(<Watchlist />, "/watchlist");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    watchlistMock.list.mockResolvedValueOnce(page([]) as never);
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText(/your watchlist is empty/i)).toBeInTheDocument();
  });

  it("removes a coin and confirms it", async () => {
    useWatchlistStore.setState({ ids: [COIN_BTC] });
    watchlistMock.list.mockResolvedValue(page([watchItem()]) as never);
    watchlistMock.remove.mockResolvedValue(undefined);
    renderAt(<Watchlist />, "/watchlist");
    await userEvent.setup().click(await screen.findByRole("button", { name: /remove bitcoin from watchlist/i }));
    expect(watchlistMock.remove).toHaveBeenCalledWith(COIN_BTC);
    expect(await screen.findByText(/removed from your watchlist/i)).toBeInTheDocument();
    expect(screen.getByText(/your watchlist is empty/i)).toBeInTheDocument();
  });
});

describe("Portfolio page", () => {
  it("shows the empty state", async () => {
    portfolioMock.get.mockResolvedValue(portfolio([]));
    renderAt(<Portfolio />, "/portfolio");
    expect(await screen.findByText(/your portfolio is empty\. add your first holding to start tracking performance/i)).toBeInTheDocument();
  });

  it("shows totals, holdings and allocation exactly as the backend calculated them", async () => {
    portfolioMock.get.mockResolvedValue(portfolio());
    renderAt(<Portfolio />, "/portfolio");
    expect(await screen.findByText("Total value")).toBeInTheDocument();
    const row = screen.getByRole("row", { name: /bitcoin/i });
    expect(within(row).getByText("$200.00")).toBeInTheDocument();
    expect(screen.getByText("Asset allocation")).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("is honest about holdings with no price (no guessed value) and says totals are partial", async () => {
    const noPrice = holding({ has_price: false, current_price: null, current_value: null, unrealized_pnl: null, unrealized_pnl_pct: null, allocation_pct: null });
    portfolioMock.get.mockResolvedValue(portfolio([noPrice], { is_partial: true, unpriced_count: 1, total_unrealized_pnl: null, total_unrealized_pnl_pct: null }));
    renderAt(<Portfolio />, "/portfolio");
    expect(await screen.findByText("No price")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/1 of 1 holdings have no market price/i);
  });

  it("shows an error with Retry", async () => {
    portfolioMock.get.mockRejectedValueOnce(new ApiError("down", 503));
    renderAt(<Portfolio />, "/portfolio");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    portfolioMock.get.mockResolvedValueOnce(portfolio([]));
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText(/your portfolio is empty/i)).toBeInTheDocument();
  });

  it("rejects invalid quantities in the form without calling the API", async () => {
    portfolioMock.get.mockResolvedValue(portfolio([]));
    renderAt(<Portfolio />, "/portfolio");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /add holding/i }));
    const form = screen.getByRole("form", { name: /add holding/i });
    await user.type(within(form).getByLabelText("Quantity"), "-3");
    await user.type(within(form).getByLabelText(/buy price/i), "10");
    await user.click(within(form).getByRole("button", { name: /add holding/i }));
    expect(await within(form).findByRole("alert")).toHaveTextContent(/choose a coin|quantity must be/i);
    expect(portfolioMock.add).not.toHaveBeenCalled();
  });

  it("edits a holding and reloads from the server", async () => {
    portfolioMock.get.mockResolvedValue(portfolio());
    portfolioMock.update.mockResolvedValue(holding({ quantity: 5 }));
    renderAt(<Portfolio />, "/portfolio");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /edit bitcoin holding/i }));
    const form = screen.getByRole("form", { name: /edit holding/i });
    const quantity = within(form).getByLabelText("Quantity");
    await user.clear(quantity);
    await user.type(quantity, "5");
    await user.click(within(form).getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(portfolioMock.update).toHaveBeenCalledWith(COIN_BTC, expect.objectContaining({ quantity: 5 })));
    await waitFor(() => expect(portfolioMock.get).toHaveBeenCalledTimes(2));
  });

  it("removes a holding only after confirmation", async () => {
    portfolioMock.get.mockResolvedValue(portfolio());
    portfolioMock.remove.mockResolvedValue(undefined);
    renderAt(<Portfolio />, "/portfolio");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /remove bitcoin from portfolio/i }));
    expect(portfolioMock.remove).not.toHaveBeenCalled();
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(portfolioMock.remove).toHaveBeenCalledWith(COIN_BTC));
  });
});

describe("hand-off from Coin Details", () => {
  const coin = { id: COIN_BTC, name: "Bitcoin", symbol: "btc", logo_url: null };

  it("opens the Portfolio add form with the coin already chosen", async () => {
    portfolioMock.get.mockResolvedValue(portfolio([]));
    renderAt(<Portfolio />, { path: "/portfolio", state: { addCoin: coin } });
    const form = await screen.findByRole("form", { name: /add holding/i });
    expect(within(form).getByText("Bitcoin")).toBeInTheDocument();
  });

  it("opens the Alerts form with the coin already chosen", async () => {
    alertsMock.list.mockResolvedValue(alertList([]));
    renderAt(<Alerts />, { path: "/alerts", state: { alertCoin: coin } });
    const form = await screen.findByRole("form", { name: /new price alert/i });
    expect(within(form).getByText("Bitcoin")).toBeInTheDocument();
  });
});

describe("History page", () => {
  it("shows the empty state", async () => {
    historyMock.list.mockResolvedValue(page([]) as never);
    renderAt(<History />, "/history");
    expect(await screen.findByText("No analysis history yet.")).toBeInTheDocument();
  });

  it("lists entries with decision, risk and a link into the right Coin Details section", async () => {
    historyMock.list.mockResolvedValue(page([historyEntry()]) as never);
    renderAt(<History />, "/history");
    const link = await screen.findByRole("link", { name: /bitcoin/i });
    expect(link).toHaveAttribute("href", `/coins/${COIN_BTC}#coin-risk-decision`);
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("LOW")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("shows an error with Retry", async () => {
    historyMock.list.mockRejectedValueOnce(new ApiError("boom", 500));
    renderAt(<History />, "/history");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("deletes an entry and reloads", async () => {
    historyMock.list.mockResolvedValue(page([historyEntry()]) as never);
    historyMock.remove.mockResolvedValue(undefined);
    renderAt(<History />, "/history");
    await userEvent.setup().click(await screen.findByRole("button", { name: /delete bitcoin entry/i }));
    await waitFor(() => expect(historyMock.remove).toHaveBeenCalledWith("h".repeat(24)));
    await waitFor(() => expect(historyMock.list).toHaveBeenCalledTimes(2));
  });

  it("filters by analysis type from page 1", async () => {
    historyMock.list.mockResolvedValue(page([]) as never);
    renderAt(<History />, "/history");
    await screen.findByText("No analysis history yet.");
    await userEvent.setup().selectOptions(screen.getByLabelText(/filter by analysis type/i), "prediction");
    await waitFor(() => expect(historyMock.list).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, analysisType: "prediction" })));
  });
});

describe("Alerts page", () => {
  it("shows the empty state", async () => {
    alertsMock.list.mockResolvedValue(alertList([]));
    renderAt(<Alerts />, "/alerts");
    expect(await screen.findByText("No alerts configured.")).toBeInTheDocument();
  });

  it("lists alerts and deletes one", async () => {
    alertsMock.list.mockResolvedValue(alertList([alert()]));
    alertsMock.remove.mockResolvedValue(undefined);
    renderAt(<Alerts />, "/alerts");
    expect(await screen.findByText(/price above \$120,000\.00/i)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /delete alert for bitcoin/i }));
    await waitFor(() => expect(alertsMock.remove).toHaveBeenCalledWith("c".repeat(24)));
  });

  it("disables an active alert", async () => {
    alertsMock.list.mockResolvedValue(alertList([alert()]));
    alertsMock.update.mockResolvedValue(alert({ status: "DISABLED" }));
    renderAt(<Alerts />, "/alerts");
    await userEvent.setup().click(await screen.findByRole("button", { name: /disable alert for bitcoin/i }));
    await waitFor(() => expect(alertsMock.update).toHaveBeenCalledWith("c".repeat(24), { status: "DISABLED" }));
  });

  it("shows the triggered banner (settings on) with the price it triggered at", async () => {
    alertsMock.list.mockResolvedValue(alertList([alert({ status: "TRIGGERED", triggered_at: "2026-10-09T00:00:00Z", triggered_price: 121000 })]));
    renderAt(<Alerts />, "/alerts");
    expect(await screen.findByText("1 alert has triggered.")).toBeInTheDocument();
    expect(screen.getByText(/at \$121,000\.00/)).toBeInTheDocument();
  });

  it("'Check now' reports what the real check did, including skipped alerts", async () => {
    alertsMock.list.mockResolvedValue(alertList([alert()]));
    alertsMock.check.mockResolvedValue({ checked: 1, triggered: 0, expired: 0, skipped_no_price: 1, skipped_stale: 0, triggered_alert_ids: [], checked_at: "2026-10-09T00:00:00Z" });
    renderAt(<Alerts />, "/alerts");
    await userEvent.setup().click(await screen.findByRole("button", { name: /check now/i }));
    expect(await screen.findByText(/checked 1 alert against current market data: 0 triggered; 1 skipped/i)).toBeInTheDocument();
  });

  it("rejects an invalid target price without calling the API", async () => {
    alertsMock.list.mockResolvedValue(alertList([]));
    renderAt(<Alerts />, "/alerts");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /new alert/i }));
    const form = screen.getByRole("form", { name: /new price alert/i });
    await user.type(within(form).getByLabelText(/target price/i), "0");
    await user.click(within(form).getByRole("button", { name: /create alert/i }));
    expect(await within(form).findByRole("alert")).toBeInTheDocument();
    expect(alertsMock.create).not.toHaveBeenCalled();
  });

  it("shows an error with Retry", async () => {
    alertsMock.list.mockRejectedValueOnce(new ApiError("boom", 500));
    renderAt(<Alerts />, "/alerts");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("Profile page", () => {
  const profile = { id: USER.id, name: USER.name, email: USER.email, role: "user", created_at: "2026-01-01T00:00:00Z" };

  it("shows the name and a read-only email", async () => {
    profileMock.get.mockResolvedValue(profile);
    renderAt(<Profile />, "/profile");
    expect(await screen.findByLabelText("Name")).toHaveValue("Test User");
    expect(screen.getByLabelText("Email")).toBeDisabled();
  });

  it("saves a new name and updates the signed-in user", async () => {
    profileMock.get.mockResolvedValue(profile);
    profileMock.updateName.mockResolvedValue({ ...profile, name: "New Name" });
    renderAt(<Profile />, "/profile");
    const user = userEvent.setup();
    const name = await screen.findByLabelText("Name");
    await user.clear(name);
    await user.type(name, "New Name");
    await user.click(screen.getByRole("button", { name: /save changes/i }));
    expect(await screen.findByText("Profile updated.")).toBeInTheDocument();
    expect(profileMock.updateName).toHaveBeenCalledWith("New Name");
  });

  it("validates the password form on the client, and shows the server's message for a wrong current password", async () => {
    profileMock.get.mockResolvedValue(profile);
    renderAt(<Profile />, "/profile");
    const user = userEvent.setup();
    const form = await screen.findByRole("form", { name: /change password/i });
    await user.click(within(form).getByRole("button", { name: /change password/i }));
    expect(await within(form).findByText(/enter your current password/i)).toBeInTheDocument();
    expect(profileMock.changePassword).not.toHaveBeenCalled();

    profileMock.changePassword.mockRejectedValue(new ApiError("Your current password is incorrect.", 400, "CURRENT_PASSWORD_INCORRECT"));
    await user.type(within(form).getByLabelText("Current password"), "wrong-password");
    await user.type(within(form).getByLabelText("New password"), "brand-new-pass-9");
    await user.type(within(form).getByLabelText("Confirm new password"), "brand-new-pass-9");
    await user.click(within(form).getByRole("button", { name: /change password/i }));
    expect(await within(form).findByText(/current password is incorrect/i)).toBeInTheDocument();
  });

  it("clears the fields after a successful password change", async () => {
    profileMock.get.mockResolvedValue(profile);
    profileMock.changePassword.mockResolvedValue(undefined);
    renderAt(<Profile />, "/profile");
    const user = userEvent.setup();
    const form = await screen.findByRole("form", { name: /change password/i });
    await user.type(within(form).getByLabelText("Current password"), "old-password-1");
    await user.type(within(form).getByLabelText("New password"), "brand-new-pass-9");
    await user.type(within(form).getByLabelText("Confirm new password"), "brand-new-pass-9");
    await user.click(within(form).getByRole("button", { name: /change password/i }));
    expect(await within(form).findByText("Password changed.")).toBeInTheDocument();
    expect(within(form).getByLabelText("Current password")).toHaveValue("");
  });

  it("shows an error with Retry when the profile can't load", async () => {
    profileMock.get.mockRejectedValueOnce(new ApiError("boom", 500));
    renderAt(<Profile />, "/profile");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("Settings page", () => {
  it("saves the theme to the account and applies it", async () => {
    settingsMock.update.mockResolvedValue({ theme: "dark", notifications: { price_alerts: true } });
    renderAt(<Settings />, "/settings");
    await userEvent.setup().click(await screen.findByRole("radio", { name: "dark" }));
    await waitFor(() => expect(settingsMock.update).toHaveBeenCalledWith({ theme: "dark" }));
    await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(true));
    expect(localStorage.getItem("crypto_ai_platform_theme")).toBe("dark");
  });

  it("saves the notification preference", async () => {
    settingsMock.update.mockResolvedValue({ theme: null, notifications: { price_alerts: false } });
    renderAt(<Settings />, "/settings");
    await userEvent.setup().click(await screen.findByRole("checkbox", { name: /banner on the alerts page/i }));
    await waitFor(() => expect(settingsMock.update).toHaveBeenCalledWith({ notifications: { price_alerts: false } }));
  });
});
