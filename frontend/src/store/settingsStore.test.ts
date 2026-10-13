import { beforeEach, describe, expect, it, vi } from "vitest";

import { settingsApi } from "../services/api/settings.api";
import { ApiError } from "../types/apiError";
import { DEFAULT_SETTINGS, useSettingsStore } from "./settingsStore";

vi.mock("../services/api/settings.api", () => ({ settingsApi: { get: vi.fn(), update: vi.fn() } }));
const api = vi.mocked(settingsApi);

beforeEach(() => {
  vi.clearAllMocks();
  useSettingsStore.getState().reset();
});

describe("settingsStore", () => {
  it("loads the saved settings", async () => {
    api.get.mockResolvedValue({ theme: "dark", notifications: { price_alerts: false } });
    await useSettingsStore.getState().load("u1");
    expect(useSettingsStore.getState()).toMatchObject({ status: "ready", settings: { theme: "dark", notifications: { price_alerts: false } } });
  });

  it("falls back to defaults and an error state when loading fails", async () => {
    api.get.mockRejectedValue(new ApiError("boom", 500));
    await useSettingsStore.getState().load("u1");
    expect(useSettingsStore.getState().status).toBe("error");
    expect(useSettingsStore.getState().settings).toEqual(DEFAULT_SETTINGS);
  });

  it("saves a change and keeps the server's answer", async () => {
    useSettingsStore.setState({ userId: "u1", status: "ready" });
    api.update.mockResolvedValue({ theme: "dark", notifications: { price_alerts: true } });
    expect(await useSettingsStore.getState().update({ theme: "dark" })).toBe(true);
    expect(api.update).toHaveBeenCalledWith({ theme: "dark" });
    expect(useSettingsStore.getState().settings.theme).toBe("dark");
  });

  it("rolls back and reports an error if saving fails", async () => {
    useSettingsStore.setState({ userId: "u1", status: "ready" });
    api.update.mockRejectedValue(new ApiError("down", 500));
    expect(await useSettingsStore.getState().update({ theme: "dark" })).toBe(false);
    expect(useSettingsStore.getState().settings.theme).toBeNull();
    expect(useSettingsStore.getState().saveError).toBeTruthy();
  });

  it("clears everything on logout", async () => {
    api.get.mockResolvedValue({ theme: "dark", notifications: { price_alerts: true } });
    await useSettingsStore.getState().load("u1");
    await useSettingsStore.getState().load(null);
    expect(useSettingsStore.getState()).toMatchObject({ userId: null, status: "idle", settings: DEFAULT_SETTINGS });
  });
});
