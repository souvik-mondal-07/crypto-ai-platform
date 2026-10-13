import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchAiAnalysis, generateAiAnalysis } from "./aiAnalysis.api";
import { apiClient } from "./client";
import { buildAiAnalysis } from "../../test-fixtures/aiAnalysis";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));
const mockedGet = vi.mocked(apiClient.get);
const mockedPost = vi.mocked(apiClient.post);

beforeEach(() => vi.clearAllMocks());

describe("AI analysis API", () => {
  it("reads the stored analysis from the backend only", async () => {
    const body = buildAiAnalysis();
    mockedGet.mockResolvedValue({ data: body });
    await expect(fetchAiAnalysis("abc")).resolves.toEqual(body);
    expect(mockedGet).toHaveBeenCalledWith("/ai-analysis/abc", expect.anything());
  });

  it("generates through the backend with a long timeout and no force by default", async () => {
    mockedPost.mockResolvedValue({ data: buildAiAnalysis() });
    await generateAiAnalysis("abc");
    const [url, , config] = mockedPost.mock.calls[0];
    expect(url).toBe("/ai-analysis/abc/generate");
    expect(config).toMatchObject({ params: undefined, timeout: 60_000 });
  });

  it("sends force_refresh only when requested", async () => {
    mockedPost.mockResolvedValue({ data: buildAiAnalysis() });
    await generateAiAnalysis("abc", { forceRefresh: true });
    expect(mockedPost.mock.calls[0][2]).toMatchObject({ params: { force_refresh: true } });
  });
});
