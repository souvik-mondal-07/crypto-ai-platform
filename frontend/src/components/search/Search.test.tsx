import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { CommandPalette } from "./CommandPalette";
import { GlobalSearch } from "./GlobalSearch";
import * as coinsApi from "../../services/api/coins.api";
import { resetDedupe } from "../../utils/dedupe";

vi.mock("../../services/api/coins.api", () => ({
  fetchCoins: vi.fn(),
  searchCoins: vi.fn(),
  fetchCoinById: vi.fn(),
}));

const mockedCoinsApi = vi.mocked(coinsApi);

function result(overrides = {}) {
  return {
    id: "coin-btc", name: "Bitcoin From Backend", symbol: "BTC", logo_url: null, market_cap_rank: 1,
    price_usd: 50000, percent_change_24h: 2.5, percent_change_7d: null, market_cap_usd: 1e12,
    volume_24h_usd: 1e10, high_24h_usd: null, low_24h_usd: null,
    ...overrides,
  } as never;
}

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function renderWithRoutes(ui: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={["/start"]}>
      <Routes>
        <Route path="*" element={<>{ui}<Where /></>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  resetDedupe();
});

describe("GlobalSearch", () => {
  it("shows real suggestions with name, symbol, rank and price", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [result()], query: "bit", count: 1 });
    const user = userEvent.setup();
    renderWithRoutes(<GlobalSearch />);

    await user.type(screen.getByRole("combobox", { name: /search coins/i }), "bit");

    const option = await screen.findByRole("option", { name: /Bitcoin From Backend/ }, { timeout: 2000 });
    expect(option).toHaveTextContent("BTC");
    expect(option).toHaveTextContent("Rank #1");
    expect(option).toHaveTextContent("$50,000.00");
  });

  it("navigates with the keyboard: ArrowDown highlights, Enter opens the coin", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({
      items: [result(), result({ id: "coin-eth", name: "Second Coin", symbol: "SEC", market_cap_rank: 2 })],
      query: "co", count: 2,
    });
    const user = userEvent.setup();
    renderWithRoutes(<GlobalSearch />);

    await user.type(screen.getByRole("combobox"), "co");
    await screen.findByRole("option", { name: /Second Coin/ }, { timeout: 2000 });

    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(screen.getByRole("option", { name: /Second Coin/ })).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{Enter}");
    expect(screen.getByTestId("where")).toHaveTextContent("/coins/coin-eth");
  });

  it("Enter with nothing highlighted keeps the old behaviour: go to /markets?q=", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [], query: "eth", count: 0 });
    const user = userEvent.setup();
    renderWithRoutes(<GlobalSearch />);

    await user.type(screen.getByRole("combobox"), "eth{Enter}");
    expect(screen.getByTestId("where")).toHaveTextContent("/markets?q=eth");
  });

  it("Escape closes the suggestion list", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [result()], query: "bit", count: 1 });
    const user = userEvent.setup();
    renderWithRoutes(<GlobalSearch />);

    await user.type(screen.getByRole("combobox"), "bit");
    await screen.findByRole("listbox", {}, { timeout: 2000 });
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("shows a no-results state", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [], query: "zzzz", count: 0 });
    const user = userEvent.setup();
    renderWithRoutes(<GlobalSearch />);

    await user.type(screen.getByRole("combobox"), "zzzz");
    expect(await screen.findByText(/no coins match/i, {}, { timeout: 2000 })).toBeInTheDocument();
  });

  it("shows a retryable error when the search request fails", async () => {
    mockedCoinsApi.searchCoins.mockRejectedValueOnce(new Error("Search is down"));
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [result()], query: "bit", count: 1 });
    const user = userEvent.setup();
    renderWithRoutes(<GlobalSearch />);

    await user.type(screen.getByRole("combobox"), "bit");
    expect(await screen.findByText("Search is down", {}, { timeout: 2000 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByRole("option", { name: /Bitcoin From Backend/ })).toBeInTheDocument();
  });

  it("does not call the backend for every keystroke", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [], query: "bitcoin", count: 0 });
    const user = userEvent.setup();
    renderWithRoutes(<GlobalSearch />);

    await user.type(screen.getByRole("combobox"), "bitcoin");
    await waitFor(() => expect(mockedCoinsApi.searchCoins).toHaveBeenCalled(), { timeout: 2000 });
    expect(mockedCoinsApi.searchCoins.mock.calls.length).toBeLessThan(3);
  });
});

describe("CommandPalette (Ctrl+K)", () => {
  it("opens with Ctrl+K, lists only real destinations, and closes with Escape", async () => {
    const user = userEvent.setup();
    renderWithRoutes(<CommandPalette />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.keyboard("{Control>}k{/Control}");
    expect(screen.getByRole("dialog", { name: /command palette/i })).toBeInTheDocument();

    for (const label of ["Open Dashboard", "Open Markets", "Open Watchlist", "Compare coins", "View Gainers", "View Losers"]) {
      expect(screen.getByRole("option", { name: new RegExp(label) })).toBeInTheDocument();
    }

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("filters actions as you type and runs the highlighted one with Enter", async () => {
    const user = userEvent.setup();
    renderWithRoutes(<CommandPalette />);

    await user.keyboard("{Control>}k{/Control}");
    await user.keyboard("gain");
    expect(screen.queryByRole("option", { name: /Open Dashboard/ })).not.toBeInTheDocument();

    await user.keyboard("{Enter}");
    expect(screen.getByTestId("where")).toHaveTextContent("/markets?tab=gainers");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("finds coins through the real search endpoint and opens Coin Details", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [result({ id: "found-id", name: "Findable Coin" })], query: "find", count: 1 });
    const user = userEvent.setup();
    renderWithRoutes(<CommandPalette />);

    await user.keyboard("{Control>}k{/Control}");
    await user.keyboard("find");
    await user.click(await screen.findByRole("option", { name: /Findable Coin/ }, { timeout: 2000 }));
    expect(screen.getByTestId("where")).toHaveTextContent("/coins/found-id");
  });
});
