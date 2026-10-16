import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { curve } from "../../test-fixtures/backtesting";
import { EquityCurveChart } from "./EquityCurveChart";

describe("EquityCurveChart", () => {
  it("draws one polyline vertex per API point for strategy and benchmark", () => {
    render(<EquityCurveChart strategy={curve([10000, 10400, 10100, 11000, 11250])} benchmark={curve([10000, 10200, 10300, 10600, 10800])} />);
    const chart = screen.getByRole("img", { name: "Equity curve with 5 points from $10,000.00 to $11,250.00" });
    expect(chart).toBeInTheDocument();
    const strategy = screen.getByTestId("strategy-line");
    const benchmark = screen.getByTestId("benchmark-line");
    expect(strategy).toHaveAttribute("data-points", "5");
    expect(benchmark).toHaveAttribute("data-points", "5");
    expect(strategy.getAttribute("points")?.split(" ")).toHaveLength(5);
    expect(screen.getByText(/Benchmark \(equal-weight buy & hold\)/)).toBeInTheDocument();
    expect(screen.getByText("$11,250.00", { selector: "text" })).toBeInTheDocument();   // axis max
  });

  it("omits the benchmark line when the API returned no benchmark", () => {
    render(<EquityCurveChart strategy={curve([100, 110])} benchmark={[]} />);
    expect(screen.queryByTestId("benchmark-line")).not.toBeInTheDocument();
    expect(screen.getByTestId("strategy-line")).toBeInTheDocument();
  });

  it("says so instead of drawing when there are too few points", () => {
    render(<EquityCurveChart strategy={curve([100])} benchmark={[]} />);
    expect(screen.getByText("Not enough points to draw an equity curve.")).toBeInTheDocument();
    expect(screen.queryByTestId("equity-chart")).not.toBeInTheDocument();
  });
});
