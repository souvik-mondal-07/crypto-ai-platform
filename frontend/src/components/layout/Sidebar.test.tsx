import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { NAV_ITEMS } from "./navigation";
import { Sidebar } from "./Sidebar";

const ROUTES = ["/dashboard", "/markets", "/watchlist", "/portfolio", "/alerts", "/news", "/history", "/backtesting", "/settings", "/profile"];

function renderSidebar(props: { mobileOpen?: boolean; onMobileClose?: () => void; path?: string; alertCount?: number } = {}) {
  const onMobileClose = props.onMobileClose ?? vi.fn();
  render(
    <MemoryRouter initialEntries={[props.path ?? "/markets"]}>
      <Sidebar mobileOpen={props.mobileOpen ?? false} onMobileClose={onMobileClose} alertCount={props.alertCount} />
    </MemoryRouter>
  );
  return { onMobileClose };
}

describe("Sidebar", () => {
  it("lists every primary destination in the Main navigation, linking only to real routes", () => {
    renderSidebar();
    const main = screen.getByRole("navigation", { name: "Main" });
    for (const item of NAV_ITEMS) {
      const link = within(main).getByRole("link", { name: item.label });
      expect(link).toHaveAttribute("href", item.to);
      expect(ROUTES).toContain(item.to);
    }
  });

  it("marks the current page and offers Settings in the footer", () => {
    renderSidebar({ path: "/portfolio" });
    expect(screen.getByRole("link", { name: "Portfolio" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Markets" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
  });

  it("renders the mobile drawer only when open, as a labelled modal dialog", () => {
    renderSidebar({ mobileOpen: false });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("the open drawer has its own navigation, focuses inside, and closes on Escape", async () => {
    const { onMobileClose } = renderSidebar({ mobileOpen: true });
    const dialog = screen.getByRole("dialog", { name: "Navigation menu" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(within(dialog).getByRole("navigation", { name: "Mobile" })).toBeInTheDocument();
    expect(dialog.contains(document.activeElement)).toBe(true);
    onMobileClose.mockClear(); // ignore the close the route-change effect fires on mount
    await userEvent.setup().keyboard("{Escape}");
    expect(onMobileClose).toHaveBeenCalled();
  });

  it("badges Alerts with the active-alert count, and shows no badge when there are none", () => {
    const { unmount } = render(
      <MemoryRouter>
        <Sidebar mobileOpen={false} onMobileClose={vi.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Alerts" })).toBeInTheDocument();
    unmount();

    renderSidebar({ alertCount: 3 });
    const link = screen.getByRole("link", { name: "Alerts (3 active)" });
    expect(link).toHaveAttribute("href", "/alerts");
    expect(link).toHaveTextContent("3");
  });

  it("offers the Gemini panel with a working Explore AI Analysis link", () => {
    renderSidebar();
    expect(screen.getByText("Powered by Gemini AI")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /explore ai analysis/i })).toHaveAttribute("href", "/markets");
  });
});
