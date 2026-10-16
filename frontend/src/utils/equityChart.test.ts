import { describe, expect, it } from "vitest";

import { curve } from "../test-fixtures/backtesting";
import { HEIGHT, PAD, WIDTH, buildChartPaths } from "./equityChart";

describe("buildChartPaths", () => {
  it("returns null without data and never invents points", () => {
    expect(buildChartPaths([], [])).toBeNull();
  });

  it("maps exactly the supplied points onto a shared scale (min at the bottom, max at the top)", () => {
    const strategy = curve([100, 150, 200]);
    const benchmark = curve([100, 120, 140]);
    const paths = buildChartPaths(strategy, benchmark)!;
    const pts = paths.strategy.split(" ").map((p) => p.split(",").map(Number));
    expect(pts).toHaveLength(3);
    expect(pts[0][0]).toBeCloseTo(PAD.left, 1);
    expect(pts[2][0]).toBeCloseTo(WIDTH - PAD.right, 1);
    expect(pts[0][1]).toBeCloseTo(HEIGHT - PAD.bottom, 1);   // 100 is the overall minimum
    expect(pts[2][1]).toBeCloseTo(PAD.top, 1);               // 200 is the overall maximum
    expect(paths.benchmark.split(" ")).toHaveLength(3);
    expect(paths.minV).toBe(100);
    expect(paths.maxV).toBe(200);
  });

  it("handles a flat curve without dividing by zero", () => {
    const paths = buildChartPaths(curve([100, 100]), [])!;
    expect(paths.strategy).not.toContain("NaN");
  });
});
