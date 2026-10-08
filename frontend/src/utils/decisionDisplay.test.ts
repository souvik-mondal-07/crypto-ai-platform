import { describe, expect, it } from "vitest";

import {
  decisionTone,
  formatSignedScore,
  predictionMissingButDecided,
  riskLevelLabel,
  riskScoreTone,
  riskTone,
  signalLabel,
  signalTone,
  statusTitle,
  unusableInputs,
} from "./decisionDisplay";
import { buildDecision, buildDecisionWithoutPrediction, buildInsufficientDecision } from "../test-fixtures/decisions";

describe("decisionDisplay", () => {
  it("formats signed scores without inventing a number for null", () => {
    expect(formatSignedScore(68.4)).toBe("+68");
    expect(formatSignedScore(-12.6)).toBe("-13");
    expect(formatSignedScore(0)).toBe("0");
    expect(formatSignedScore(null)).toBe("Unavailable");
  });

  it("labels risk levels and signals", () => {
    expect(riskLevelLabel("VERY_HIGH")).toBe("Very high");
    expect(riskLevelLabel(null)).toBe("Unavailable");
    expect(signalLabel("BULLISH")).toBe("Bullish");
    expect(signalLabel("UNAVAILABLE")).toBe("Unavailable");
  });

  it("maps tones", () => {
    expect(decisionTone("BUY")).toBe("positive");
    expect(decisionTone("SELL")).toBe("negative");
    expect(decisionTone("HOLD")).toBe("neutral");
    expect(decisionTone(null)).toBe("muted");
    expect(riskTone("LOW")).toBe("positive");
    expect(riskTone("VERY_HIGH")).toBe("negative");
    expect(riskScoreTone(20)).toBe("positive");
    expect(riskScoreTone(50)).toBe("neutral");
    expect(riskScoreTone(75)).toBe("negative");
    expect(signalTone("WEAK")).toBe("negative");
    expect(signalTone("UNAVAILABLE")).toBe("muted");
  });

  it("titles every non-valid status", () => {
    expect(statusTitle("INSUFFICIENT_DATA")).toBe("Insufficient data");
    expect(statusTitle("STALE_DATA")).toBe("Data is out of date");
    expect(statusTitle("PREDICTION_UNAVAILABLE")).toBe("ML prediction unavailable");
    expect(statusTitle("ANALYSIS_UNAVAILABLE")).toBe("Analysis unavailable");
  });

  it("lists only the inputs that could not be used", () => {
    expect(unusableInputs(buildDecision())).toEqual([]);
    expect(unusableInputs(buildInsufficientDecision()).map((i) => i.key)).toEqual(["fundamental", "sentiment", "prediction"]);
  });

  it("detects a decision made without the prediction", () => {
    expect(predictionMissingButDecided(buildDecision())).toBe(false);
    expect(predictionMissingButDecided(buildDecisionWithoutPrediction())).toBe(true);
    expect(predictionMissingButDecided(buildInsufficientDecision())).toBe(false);
  });
});
