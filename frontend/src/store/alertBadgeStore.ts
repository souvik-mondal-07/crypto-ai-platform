import { create } from "zustand";

import { alertsApi } from "../services/api/alerts.api";

/**
 * Count of the signed-in user's ACTIVE price alerts, for the sidebar / header badges. It is a convenience:
 * loaded by the Dashboard (GET /alerts?status=ACTIVE, `total` only) and then shown on every page; a failed load simply
 * leaves no badge. It is tied to a user id so one account's count is never shown to another.
 */
interface AlertBadgeState {
  userId: string | null;
  count: number;
  load: (userId: string | null) => Promise<void>;
}

let seq = 0;

export const useAlertBadgeStore = create<AlertBadgeState>((set) => ({
  userId: null,
  count: 0,
  load: async (userId) => {
    const mine = ++seq;
    if (!userId) {
      set({ userId: null, count: 0 });
      return;
    }
    try {
      const result = await alertsApi.list(1, 1, "ACTIVE");
      if (mine !== seq) return;
      set({ userId, count: typeof result?.total === "number" ? result.total : 0 });
    } catch {
      if (mine === seq) set({ userId, count: 0 });
    }
  },
}));
