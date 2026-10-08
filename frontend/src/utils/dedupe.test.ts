import { beforeEach, describe, expect, it } from "vitest";

import { dedupe, resetDedupe } from "./dedupe";

beforeEach(() => resetDedupe());

describe("dedupe", () => {
  it("shares one request between concurrent callers with the same key", async () => {
    let calls = 0;
    const slow = () => new Promise<number>((resolve) => setTimeout(() => resolve(++calls), 10));
    const results = await Promise.all([dedupe("k", slow), dedupe("k", slow), dedupe("k", slow)]);
    expect(calls).toBe(1);
    expect(results).toEqual([1, 1, 1]);
  });

  it("is not a cache: the next call after settling makes a fresh request", async () => {
    let calls = 0;
    const fast = () => Promise.resolve(++calls);
    expect(await dedupe("k", fast)).toBe(1);
    expect(await dedupe("k", fast)).toBe(2);
  });

  it("does not share between different keys", async () => {
    let calls = 0;
    const fast = () => Promise.resolve(++calls);
    await Promise.all([dedupe("a", fast), dedupe("b", fast)]);
    expect(calls).toBe(2);
  });

  it("a rejection reaches every waiter and does not poison the key", async () => {
    const failing = () => Promise.reject(new Error("boom"));
    const outcomes = await Promise.allSettled([dedupe("k", failing), dedupe("k", failing)]);
    expect(outcomes.every((outcome) => outcome.status === "rejected")).toBe(true);
    expect(await dedupe("k", () => Promise.resolve(7))).toBe(7);
  });

  it("turns a synchronous throw into a rejection", async () => {
    await expect(dedupe("k", () => { throw new Error("sync"); })).rejects.toThrow("sync");
  });
});
