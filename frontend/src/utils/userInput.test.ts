import { describe, expect, it } from "vitest";

import { parseNonNegative, parsePositive, validatePasswordChange } from "./userInput";

describe("parsePositive / parseNonNegative", () => {
  it("accepts valid numbers", () => {
    expect(parsePositive("0.5")).toBe(0.5);
    expect(parseNonNegative("0")).toBe(0);
    expect(parseNonNegative(" 12.5 ")).toBe(12.5);
  });
  it.each(["", "  ", "abc", "-1", "NaN", "Infinity", "1e999"])("rejects %j", (raw) => {
    expect(parseNonNegative(raw)).toBeNull();
  });
  it("positive rejects zero", () => {
    expect(parsePositive("0")).toBeNull();
  });
});

describe("validatePasswordChange", () => {
  const ok = { current: "old-password", next: "new-password-1", confirm: "new-password-1" };
  it("passes valid input", () => expect(validatePasswordChange(ok)).toBeNull());
  it("requires the current password", () => expect(validatePasswordChange({ ...ok, current: "" })).toMatch(/current/i));
  it("enforces length", () => expect(validatePasswordChange({ ...ok, next: "short", confirm: "short" })).toMatch(/at least 8/));
  it("requires matching confirmation", () => expect(validatePasswordChange({ ...ok, confirm: "different-1" })).toMatch(/do not match/));
  it("rejects an unchanged password", () =>
    expect(validatePasswordChange({ current: "same-password", next: "same-password", confirm: "same-password" })).toMatch(/different/));
});
