import { describe, expect, it } from "vitest";

import { BACKEND_STALE_AFTER_MS, getFreshness } from "./freshness";

const NOW = Date.parse("2026-10-01T12:00:00Z");

describe("getFreshness", () => {
  it("reports unavailable when there is no usable timestamp", () => {
    expect(getFreshness(null).level).toBe("unavailable");
    expect(getFreshness(undefined).level).toBe("unavailable");
    expect(getFreshness("not-a-date").level).toBe("unavailable");
  });

  it("is fresh within the backend threshold and stale beyond it", () => {
    expect(getFreshness("2026-10-01T11:50:00Z", undefined, NOW)).toEqual({ level: "fresh", label: "Updated recently" });
    expect(getFreshness("2026-10-01T05:00:00Z", undefined, NOW).level).toBe("stale");
  });

  it("mirrors the backend's 6 hour STALE_AFTER and has not been loosened", () => {
    expect(BACKEND_STALE_AFTER_MS).toBe(6 * 60 * 60 * 1000);
  });

  it("prefers the backend's own is_stale flag when present", () => {
    expect(getFreshness("2026-10-01T11:59:00Z", true, NOW).level).toBe("stale");
    expect(getFreshness("2026-10-01T01:00:00Z", false, NOW).level).toBe("fresh");
  });
});
