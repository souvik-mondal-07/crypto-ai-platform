import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { decisionEvaluation, emptyDecisionEvaluation } from "../../test-fixtures/backtesting";
import { DecisionEvaluationSection } from "./DecisionEvaluationSection";

function setup(props: Partial<Parameters<typeof DecisionEvaluationSection>[0]> = {}) {
  const handlers = { onHorizon: vi.fn(), onRetry: vi.fn() };
  render(<DecisionEvaluationSection data={decisionEvaluation()} loading={false} error={null} horizon="" {...handlers} {...props} />);
  return handlers;
}

describe("DecisionEvaluationSection", () => {
  it("shows per decision/horizon metrics from the API", () => {
    setup();
    const table = within(screen.getByRole("table", { name: "Decision evaluation" }));
    const buy = table.getByRole("row", { name: /^BUY 24h/ });
    expect(buy).toHaveTextContent("40");
    expect(buy).toHaveTextContent("+1.20%");
    expect(buy).toHaveTextContent("60.0%");
    expect(table.getByRole("row", { name: /^SELL 24h/ })).toHaveTextContent("56.0%");
  });

  it("never reports HOLD as a directional success — only a neutral-band share", () => {
    setup();
    const hold = within(screen.getByRole("table", { name: "Decision evaluation" })).getByRole("row", { name: /^HOLD 24h/ });
    expect(hold).toHaveTextContent("72.0% within neutral band");
    expect(hold).not.toHaveTextContent("success");
  });

  it("marks cells below the sample minimum as insufficient and shows N/A", () => {
    setup();
    const row = within(screen.getByRole("table", { name: "Decision evaluation" })).getByRole("row", { name: /^BUY 7d/ });
    expect(row).toHaveTextContent("N/A");
    expect(row).toHaveTextContent("insufficient data");
  });

  it("documents how each decision is interpreted", () => {
    setup();
    const rules = within(screen.getByRole("list", { name: "Decision evaluation rules" }));
    expect(rules.getByText(/Directionally aligned when the price rose/)).toBeInTheDocument();
    expect(rules.getByText(/Makes no directional claim/)).toBeInTheDocument();
  });

  it("has an honest empty state", () => {
    setup({ data: emptyDecisionEvaluation() });
    expect(screen.getByText("No decisions have been stored yet, so none can be evaluated.")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Decision evaluation" })).not.toBeInTheDocument();
  });

  it("changes horizon, loads and fails with Retry", async () => {
    const { onHorizon, onRetry } = setup();
    await userEvent.setup().selectOptions(screen.getByLabelText("Decision evaluation horizon"), "7d");
    expect(onHorizon).toHaveBeenCalledWith("7d");
    render(<DecisionEvaluationSection data={null} loading={false} error="Decision evaluation could not be loaded." horizon="" onHorizon={vi.fn()} onRetry={onRetry} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalled();
    render(<DecisionEvaluationSection data={null} loading error={null} horizon="" onHorizon={vi.fn()} onRetry={vi.fn()} />);
    expect(screen.getByRole("status", { name: "Loading decision evaluation" })).toBeInTheDocument();
  });
});
