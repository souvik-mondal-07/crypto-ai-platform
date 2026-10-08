/**
 * End-to-end WIRING test for the AI Analysis section: hook -> aiAnalysis.api -> apiClient -> axios.
 *
 * Unlike AiAnalysisSection.test.tsx this does NOT mock the AI service module. Only the network
 * boundary (the axios adapter) is replaced, so it proves the section really issues
 * GET /ai-analysis/{coinId} for the coin it was given — and it runs under <StrictMode> like the dev
 * app does (effects run twice there, which is exactly where "no request is sent" bugs hide).
 */
import "@testing-library/jest-dom/vitest";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from "axios";

import { AiAnalysisSection } from "./AiAnalysisSection";
import { apiClient } from "../../services/api/client";
import { buildAiAnalysis } from "../../test-fixtures/aiAnalysis";
import type { AiAnalysisResponse } from "../../types/aiAnalysis";

const COIN = "6aaebdda09418270323674a3";

interface Seen {
  method?: string;
  url?: string;
  params?: unknown;
}

const originalAdapter = apiClient.defaults.adapter;
let seen: Seen[] = [];

function respond(handler: (config: InternalAxiosRequestConfig) => { status: number; data: unknown }) {
  const adapter: AxiosAdapter = async (config) => {
    seen.push({ method: config.method, url: config.url, params: config.params });
    if (config.signal?.aborted) throw Object.assign(new Error("canceled"), { code: "ERR_CANCELED", config });
    const { status, data } = handler(config);
    const response: AxiosResponse = { data, status, statusText: String(status), headers: {}, config, request: {} };
    if (status >= 400) throw Object.assign(new Error(`Request failed with status code ${status}`), { config, response, isAxiosError: true });
    return response;
  };
  apiClient.defaults.adapter = adapter;
}

beforeEach(() => {
  seen = [];
});
afterEach(() => {
  apiClient.defaults.adapter = originalAdapter;
});

describe("AiAnalysisSection network wiring", () => {
  it("sends GET /ai-analysis/{coinId} for the given coin and renders the response (StrictMode)", async () => {
    const body: AiAnalysisResponse = buildAiAnalysis({ coin_id: COIN });
    respond(() => ({ status: 200, data: body }));

    render(
      <StrictMode>
        <AiAnalysisSection coinId={COIN} />
      </StrictMode>,
    );

    expect(await screen.findByText(/synthetic summary/i)).toBeInTheDocument();
    const gets = seen.filter((request) => request.method === "get");
    expect(gets.length).toBeGreaterThanOrEqual(1);
    expect(gets.every((request) => request.url === `/ai-analysis/${COIN}`)).toBe(true);
    expect(seen.some((request) => request.method === "post")).toBe(false); // reading must not generate
  });

  it("generates through POST /ai-analysis/{coinId}/generate only when nothing is stored", async () => {
    const body: AiAnalysisResponse = buildAiAnalysis({ coin_id: COIN, cached: false });
    respond((config) =>
      config.method === "get"
        ? { status: 404, data: { error: { code: "AI_ANALYSIS_NOT_FOUND", message: "No AI analysis has been generated for this coin yet." } } }
        : { status: 200, data: body },
    );

    render(
      <StrictMode>
        <AiAnalysisSection coinId={COIN} />
      </StrictMode>,
    );

    expect(await screen.findByText(/synthetic summary/i)).toBeInTheDocument();
    expect(seen.some((request) => request.method === "get" && request.url === `/ai-analysis/${COIN}`)).toBe(true);
    const posts = seen.filter((request) => request.method === "post");
    expect(posts.length).toBeGreaterThanOrEqual(1);
    expect(posts.every((request) => request.url === `/ai-analysis/${COIN}/generate`)).toBe(true);
  });

  it("shows the unavailable state (not a blank section) when the backend says Gemini is unavailable", async () => {
    respond((config) =>
      config.method === "get"
        ? { status: 404, data: { error: { code: "AI_ANALYSIS_NOT_FOUND", message: "none" } } }
        : { status: 503, data: { error: { code: "AI_UNAVAILABLE", message: "The AI service is temporarily unavailable." } } },
    );
    render(
      <StrictMode>
        <AiAnalysisSection coinId={COIN} />
      </StrictMode>,
    );
    expect(await screen.findByText("AI analysis is temporarily unavailable.")).toBeInTheDocument();
  });
});
