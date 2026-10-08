import { describe, expect, it } from "vitest";

import { squarify } from "./treemap";

const area = (r: { w: number; h: number }) => r.w * r.h;

describe("squarify", () => {
  it("tiles the whole container with areas proportional to weight", () => {
    const rects = squarify(
      [
        { item: "a", weight: 50 },
        { item: "b", weight: 30 },
        { item: "c", weight: 15 },
        { item: "d", weight: 5 },
      ],
      100,
      100
    );

    expect(rects).toHaveLength(4);
    expect(rects.reduce((sum, r) => sum + area(r), 0)).toBeCloseTo(10_000, 4);
    const byItem = Object.fromEntries(rects.map((r) => [r.item, area(r)]));
    expect(byItem.a).toBeCloseTo(5_000, 3);
    expect(byItem.b).toBeCloseTo(3_000, 3);
    expect(byItem.d).toBeCloseTo(500, 3);
  });

  it("keeps every rectangle inside the container", () => {
    const rects = squarify(Array.from({ length: 40 }, (_, i) => ({ item: i, weight: 100 - i })), 100, 100);
    for (const r of rects) {
      expect(r.x).toBeGreaterThanOrEqual(-1e-9);
      expect(r.y).toBeGreaterThanOrEqual(-1e-9);
      expect(r.x + r.w).toBeLessThanOrEqual(100 + 1e-9);
      expect(r.y + r.h).toBeLessThanOrEqual(100 + 1e-9);
    }
  });

  it("gives larger weights larger tiles", () => {
    const rects = squarify(
      [
        { item: "small", weight: 1 },
        { item: "big", weight: 9 },
      ],
      100,
      100
    );
    const big = rects.find((r) => r.item === "big")!;
    const small = rects.find((r) => r.item === "small")!;
    expect(area(big)).toBeGreaterThan(area(small));
  });

  it("drops items with missing, zero, negative or non-finite weights instead of inventing a size", () => {
    const rects = squarify(
      [
        { item: "ok", weight: 10 },
        { item: "null", weight: null },
        { item: "undef", weight: undefined },
        { item: "zero", weight: 0 },
        { item: "neg", weight: -5 },
        { item: "nan", weight: Number.NaN },
      ],
      100,
      100
    );
    expect(rects.map((r) => r.item)).toEqual(["ok"]);
    expect(area(rects[0])).toBeCloseTo(10_000, 3);
  });

  it("returns an empty layout for empty input or a degenerate container", () => {
    expect(squarify([], 100, 100)).toEqual([]);
    expect(squarify([{ item: "a", weight: 1 }], 0, 100)).toEqual([]);
  });
});
