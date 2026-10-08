import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FundamentalAnalysisSection } from "./FundamentalAnalysisSection";
import { buildFundamentals, buildMetrics, metric } from "../../test-fixtures/fundamentals";
import type { FundamentalAnalysisResponse } from "../../types/fundamentals";

function renderSection(
  props: Partial<ComponentProps<typeof FundamentalAnalysisSection>> = {}
) {
  const onRetry = vi.fn();
  const onRefresh = vi.fn();
  const utils = render(
    <FundamentalAnalysisSection
      fundamentals={buildFundamentals()}
      loading={false}
      refreshing={false}
      error={null}
      notAvailable={false}
      onRetry={onRetry}
      onRefresh={onRefresh}
      {...props}
    />
  );
  return { ...utils, onRetry, onRefresh };
}

function card(name: string) {
  return screen.getByRole("heading", { name }).closest("div")!.parentElement as HTMLElement;
}

describe("FundamentalAnalysisSection — content", () => {
  it("renders every group", () => {
    renderSection();
    expect(screen.getByRole("heading", { name: "Fundamental Analysis" })).toBeInTheDocument();
    for (const title of [
      "Market Overview",
      "Supply",
      "Valuation",
      "Calculated Metrics",
      "Project Information",
      "Development & Ecosystem",
      "Fundamental Score",
      "Fundamental Summary",
    ]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
  });

  it("shows provider-reported market figures", () => {
    renderSection();
    const market = within(card("Market Overview"));
    expect(market.getByText("$1.23B")).toBeInTheDocument();
    expect(market.getByText("#12")).toBeInTheDocument();
    expect(market.getByText("$45.67M")).toBeInTheDocument();
    expect(market.getByText("$1.65B")).toBeInTheDocument();
  });

  it("labels provider-reported and calculated data separately", () => {
    renderSection();
    expect(within(card("Market Overview")).getByText("Provider-reported")).toBeInTheDocument();
    expect(within(card("Calculated Metrics")).getByText("Calculated")).toBeInTheDocument();
    expect(within(card("Fundamental Score")).getByText("Calculated")).toBeInTheDocument();
    // The Supply card mixes both and says which is which.
    const supply = within(card("Supply"));
    expect(supply.getByText("Provider-reported")).toBeInTheDocument();
    expect(supply.getByText("Calculated")).toBeInTheDocument();
  });

  it("formats calculated metrics with their units", () => {
    renderSection();
    const calc = within(card("Calculated Metrics"));
    expect(calc.getByText("0.0371 (3.71%)")).toBeInTheDocument();
    expect(calc.getByText("0.7455 (74.55%)")).toBeInTheDocument();
    expect(calc.getByText("71.43%")).toBeInTheDocument();
    expect(calc.getByText("-75.00%")).toBeInTheDocument();
    expect(calc.getByText("+400.00%")).toBeInTheDocument();
  });

  it("shows the supply figures and derived supply percentages", () => {
    renderSection();
    const supply = within(card("Supply"));
    expect(supply.getByText("Capped supply")).toBeInTheDocument();
    expect(supply.getByText("15,000,000")).toBeInTheDocument();
    expect(supply.getByText("21,000,000")).toBeInTheDocument();
    expect(supply.getByText("6,000,000")).toBeInTheDocument(); // remaining to max
    expect(supply.getByText("83.33%")).toBeInTheDocument();
  });

  it("does not repeat current price or performance already shown elsewhere on the page", () => {
    renderSection();
    const valuation = within(card("Valuation"));
    expect(valuation.getByText("$200.00")).toBeInTheDocument(); // ATH
    expect(valuation.getByText("$10.00")).toBeInTheDocument(); // ATL
    expect(valuation.getByText("-74.90%")).toBeInTheDocument(); // provider-reported
    expect(valuation.queryByText("$50.00")).not.toBeInTheDocument();
    expect(valuation.getByText(/shown at the top of this page/i)).toBeInTheDocument();
  });

  it("shows when the data was fetched and calculated, and that it is not real-time", () => {
    renderSection();
    expect(screen.getByText(/project data fetched/i)).toBeInTheDocument();
    expect(screen.getByText(/market data updated/i)).toBeInTheDocument();
    expect(screen.getByText(/calculated just now/i)).toBeInTheDocument();
    expect(screen.getByText(/not real-time/i)).toBeInTheDocument();
  });

  it("shows 'not fetched' when project data was never retrieved", () => {
    const base = buildFundamentals();
    renderSection({
      fundamentals: buildFundamentals({ timestamps: { ...base.timestamps, fetched_at: null } }),
    });
    expect(screen.getByText(/project data fetched: not fetched/i)).toBeInTheDocument();
  });
});

describe("FundamentalAnalysisSection — data quality block", () => {
  it("lists project, market and calculation freshness together under one heading", () => {
    renderSection();
    const block = screen.getByLabelText(/data quality and freshness/i);
    expect(within(block).getByText(/project data fetched/i)).toBeInTheDocument();
    expect(within(block).getByText(/market data updated/i)).toBeInTheDocument();
    expect(within(block).getByText(/calculated/i)).toBeInTheDocument();
  });

  it("warns clearly when the market data timestamp is older than the backend's stale threshold", () => {
    const base = buildFundamentals();
    renderSection({
      fundamentals: buildFundamentals({
        timestamps: { ...base.timestamps, market_data_updated_at: "2020-01-01T00:00:00Z" },
      }),
    });
    expect(screen.getByText("Market data is stale.")).toBeInTheDocument();
  });

  it("shows no stale warning when market data is recent", () => {
    const base = buildFundamentals();
    renderSection({
      fundamentals: buildFundamentals({
        timestamps: { ...base.timestamps, market_data_updated_at: new Date().toISOString() },
      }),
    });
    expect(screen.queryByText("Market data is stale.")).not.toBeInTheDocument();
  });
});

describe("FundamentalAnalysisSection — missing / partial data", () => {
  it("shows 'Not available' for a missing maximum supply instead of inventing one", () => {
    const base = buildFundamentals();
    renderSection({
      fundamentals: buildFundamentals({
        supply: { ...base.supply!, max_supply: null, supply_type: "not_reported" },
        calculated_metrics: buildMetrics({
          circulating_to_max_supply_percent: metric(null, "percent", "Maximum supply is not reported (unlimited or unknown)."),
          remaining_supply_to_max: metric(null, "tokens", "Maximum supply is not reported (unlimited or unknown)."),
        }),
      }),
    });
    const supply = within(card("Supply"));
    expect(supply.getByText("Maximum supply not reported")).toBeInTheDocument();
    expect(supply.getAllByText("Not available").length).toBeGreaterThanOrEqual(1);
    expect(supply.queryByText("Unlimited")).not.toBeInTheDocument();
  });

  it("shows 'Unlimited' only when the provider explicitly says so", () => {
    const base = buildFundamentals();
    renderSection({
      fundamentals: buildFundamentals({ supply: { ...base.supply!, max_supply: null, supply_type: "unlimited" } }),
    });
    expect(within(card("Supply")).getByText("Unlimited")).toBeInTheDocument();
    expect(within(card("Supply")).getByText("Unlimited supply (per provider)")).toBeInTheDocument();
  });

  it("explains why a calculated metric is unavailable", () => {
    renderSection({
      fundamentals: buildFundamentals({
        calculated_metrics: buildMetrics({
          market_cap_to_fdv: metric(null, "ratio", "Fully diluted valuation is not available."),
        }),
      }),
    });
    const calc = within(card("Calculated Metrics"));
    expect(calc.getByText("Fully diluted valuation is not available.")).toBeInTheDocument();
    expect(calc.getAllByText("Not available").length).toBeGreaterThanOrEqual(1);
  });

  it("renders every card with 'Not available' when the market and project sections are missing", () => {
    renderSection({
      fundamentals: buildFundamentals({
        market: null, supply: null, valuation: null, project_info: null, ecosystem: null, summary: [],
        is_partial: true, unavailable_sections: ["market", "project_info", "ecosystem"],
        warnings: ["No market data has been synchronized for this coin yet."],
      }),
    });
    for (const title of ["Market Overview", "Supply", "Valuation", "Project Information", "Development & Ecosystem", "Fundamental Summary"]) {
      expect(within(card(title)).getByText("Not available")).toBeInTheDocument();
    }
    expect(screen.getByText("No market data has been synchronized for this coin yet.")).toBeInTheDocument();
  });

  it("renders the backend's warnings as notices", () => {
    renderSection({
      fundamentals: buildFundamentals({ warnings: ["Market data has not been refreshed recently and may be out of date."] }),
    });
    expect(screen.getByText(/may be out of date/i)).toBeInTheDocument();
  });

  it("says there is no development data rather than showing zeros", () => {
    const base = buildFundamentals();
    renderSection({
      fundamentals: buildFundamentals({
        ecosystem: {
          ...base.ecosystem!,
          development: { ...base.ecosystem!.development, available: false, repositories: [], commit_count_4_weeks: 0, stars: 0 },
        },
      }),
    });
    const eco = within(card("Development & Ecosystem"));
    expect(eco.getByText(/no development data or code repository reported/i)).toBeInTheDocument();
    expect(eco.queryByText("Commits (last 4 weeks)")).not.toBeInTheDocument();
  });

  it("shows development figures when the provider reports them", () => {
    renderSection();
    const eco = within(card("Development & Ecosystem"));
    expect(eco.getByText("Commits (last 4 weeks)")).toBeInTheDocument();
    expect(eco.getByText("120")).toBeInTheDocument();
    expect(eco.getByText("8.5K closed of 9K")).toBeInTheDocument();
  });
});

describe("FundamentalAnalysisSection — provider text and links are handled safely", () => {
  it("renders the description as plain text, never as HTML", () => {
    const { container } = renderSection();
    expect(screen.getByText(/A peer-to-peer test asset\. click/)).toBeInTheDocument();
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
  });

  it("opens external links safely and drops non-http(s) URLs", () => {
    const base = buildFundamentals();
    const { container } = renderSection({
      fundamentals: buildFundamentals({
        project_info: { ...base.project_info!, homepage_urls: ["https://www.example.org", "javascript:alert(1)"] },
      }),
    });
    const link = within(card("Project Information")).getByRole("link", { name: "example.org" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(link.getAttribute("rel")).toContain("noreferrer");
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
  });

  it("shortens contract addresses but keeps the full value available", () => {
    renderSection();
    const code = within(card("Project Information")).getByText("0xc02aaa…756cc2");
    expect(code).toHaveAttribute("title", "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2");
  });

  it("collapses long descriptions behind Read more", async () => {
    const user = userEvent.setup();
    const base = buildFundamentals();
    renderSection({
      fundamentals: buildFundamentals({ project_info: { ...base.project_info!, description: "word ".repeat(200) } }),
    });
    const projectCard = within(card("Project Information"));
    expect(projectCard.getByRole("button", { name: "Read more" })).toBeInTheDocument();
    await user.click(projectCard.getByRole("button", { name: "Read more" }));
    expect(projectCard.getByRole("button", { name: "Show less" })).toBeInTheDocument();
  });
});

describe("FundamentalAnalysisSection — fundamental score", () => {
  it("shows the score, its coverage, and every component", () => {
    renderSection();
    const score = within(card("Fundamental Score"));
    expect(score.getByText("88")).toBeInTheDocument();
    expect(score.getByText("/ 100")).toBeInTheDocument();
    expect(score.getByRole("progressbar", { name: "Fundamental score" })).toHaveAttribute("aria-valuenow", "88");
    expect(score.getByText(/based on 100% of the scoring weight/i)).toBeInTheDocument();
    expect(score.getByRole("table")).toBeInTheDocument();
    expect(score.getAllByRole("row")).toHaveLength(7); // header + 6 components
  });

  it("documents how the score is calculated, in the UI", () => {
    renderSection();
    const score = within(card("Fundamental Score"));
    expect(score.getByText("How this score is calculated")).toBeInTheDocument();
    expect(score.getByText(/Market cap bands rule\./)).toBeInTheDocument();
    expect(score.getByText(/price movement is deliberately excluded/i)).toBeInTheDocument();
    expect(score.getByText(/not investment advice/i)).toBeInTheDocument();
  });

  it("shows 'Not enough data' and no number or bar when there is too little data", () => {
    const base = buildFundamentals();
    renderSection({
      fundamentals: buildFundamentals({
        score: {
          ...base.score,
          status: "not_enough_data",
          score: null,
          coverage_percent: 35,
          message: "Not enough data",
          components: base.score.components.map((c, i) => (i < 3 ? { ...c, available: false, subscore: null, points: null } : c)),
        },
      }),
    });
    const score = within(card("Fundamental Score"));
    expect(score.getByText("Not enough data")).toBeInTheDocument();
    expect(score.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(score.queryByText("/ 100")).not.toBeInTheDocument();
    expect(score.getByText(/only 35% is currently available/i)).toBeInTheDocument();
    expect(score.getAllByText("Not available").length).toBe(3);
  });
});

describe("FundamentalAnalysisSection — states", () => {
  it("shows a loading state and no content on first load", () => {
    renderSection({ fundamentals: null, loading: true });
    expect(screen.getByText("Loading fundamental analysis...")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Market Overview" })).not.toBeInTheDocument();
  });

  it("shows a clear error with a working Retry", async () => {
    const user = userEvent.setup();
    const { onRetry } = renderSection({ fundamentals: null, error: "Provider unavailable." });
    expect(screen.getByText("Provider unavailable.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows an empty state (not an error) when the coin has no fundamental data", () => {
    renderSection({ fundamentals: null, error: "No fundamental data is available.", notAvailable: true });
    expect(screen.getByText("Fundamental data is not available for this coin yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
  });

  it("never sits in a loading state once the request has finished with nothing to show", () => {
    renderSection({ fundamentals: null, loading: false, error: null });
    expect(screen.queryByText(/loading fundamental analysis/i)).not.toBeInTheDocument();
    expect(screen.getByText("Fundamental analysis is not available for this coin yet.")).toBeInTheDocument();
  });

  it("keeps existing data visible and shows a notice when a refresh fails", () => {
    renderSection({ error: "Network down." });
    expect(screen.getByText(/could not refresh: network down\./i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Market Overview" })).toBeInTheDocument();
  });

  it("keeps data on screen while refreshing and disables the refresh button", () => {
    renderSection({ refreshing: true });
    expect(screen.getByRole("heading", { name: "Market Overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refresh data/i })).toBeDisabled();
  });

  it("requests a refresh when Refresh data is clicked", async () => {
    const user = userEvent.setup();
    const { onRefresh } = renderSection();
    await user.click(screen.getByRole("button", { name: /refresh data/i }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("can be collapsed and expanded", async () => {
    const user = userEvent.setup();
    renderSection();
    const toggle = screen.getByRole("button", { name: "Collapse" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.click(toggle);
    expect(screen.queryByRole("heading", { name: "Market Overview" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand" }));
    expect(screen.getByRole("heading", { name: "Market Overview" })).toBeInTheDocument();
  });
});

describe("FundamentalAnalysisSection — no trading decisions", () => {
  const FORBIDDEN = /\b(buy|sell|hold|guaranteed|will (rise|fall|increase|decrease))\b/i;

  it.each<[string, FundamentalAnalysisResponse | null]>([
    ["full data", buildFundamentals()],
    ["not enough data", buildFundamentals({ score: { ...buildFundamentals().score, status: "not_enough_data", score: null, message: "Not enough data" } })],
    ["nothing available", null],
  ])("contains no BUY/HOLD/SELL or predictive wording (%s)", (_name, fundamentals) => {
    const { container } = renderSection({ fundamentals });
    expect(container.textContent ?? "").not.toMatch(FORBIDDEN);
  });
});

describe("FundamentalAnalysisSection — light and dark mode", () => {
  it("gives every surface and text colour a dark-mode counterpart", () => {
    const { container } = renderSection();
    const classed = Array.from(container.querySelectorAll<HTMLElement>("[class]"));
    const offenders = classed.filter((el) => {
      const cls = el.getAttribute("class") ?? "";
      const lightSurface = /\bbg-(white|slate-50|slate-100)\b/.test(cls);
      // text-slate-400 is a mid-grey that is legible on both themes (used bare across the app).
      const lightText = /\btext-slate-(500|600|700|800|900)\b/.test(cls);
      return (lightSurface || lightText) && !/\bdark:/.test(cls);
    });
    expect(offenders.map((el) => el.getAttribute("class"))).toEqual([]);
  });
});
