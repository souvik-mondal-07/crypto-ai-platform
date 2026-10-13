import { beforeEach, describe, expect, it, vi } from "vitest";

import { alertsApi } from "../services/api/alerts.api";
import { useAlertBadgeStore } from "./alertBadgeStore";

vi.mock("../services/api/alerts.api", () => ({ alertsApi: { list: vi.fn() } }));

const listMock = vi.mocked(alertsApi.list);

beforeEach(() => {
  vi.clearAllMocks();
  useAlertBadgeStore.setState({ userId: null, count: 0 });
});

describe("alertBadgeStore", () => {
  it("stores the backend's total of ACTIVE alerts for the user", async () => {
    listMock.mockResolvedValue({ items: [], total: 3, page: 1, limit: 1, pages: 3 });
    await useAlertBadgeStore.getState().load("u1");
    expect(listMock).toHaveBeenCalledWith(1, 1, "ACTIVE");
    expect(useAlertBadgeStore.getState()).toMatchObject({ userId: "u1", count: 3 });
  });

  it("clears the count when signed out, without calling the API", async () => {
    useAlertBadgeStore.setState({ userId: "u1", count: 3 });
    await useAlertBadgeStore.getState().load(null);
    expect(listMock).not.toHaveBeenCalled();
    expect(useAlertBadgeStore.getState()).toMatchObject({ userId: null, count: 0 });
  });

  it("shows no badge (0) when the request fails, rather than an error or a stale number", async () => {
    useAlertBadgeStore.setState({ userId: "u1", count: 3 });
    listMock.mockRejectedValue(new Error("down"));
    await useAlertBadgeStore.getState().load("u1");
    expect(useAlertBadgeStore.getState().count).toBe(0);
  });

  it("ignores a slow response that belongs to a previous load", async () => {
    let resolveFirst!: (value: never) => void;
    listMock.mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve as never; }));
    listMock.mockResolvedValueOnce({ items: [], total: 7, page: 1, limit: 1, pages: 7 });
    const first = useAlertBadgeStore.getState().load("u1");
    await useAlertBadgeStore.getState().load("u2");
    resolveFirst({ items: [], total: 99, page: 1, limit: 1, pages: 99 } as never);
    await first;
    expect(useAlertBadgeStore.getState()).toMatchObject({ userId: "u2", count: 7 });
  });
});
