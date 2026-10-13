import { create } from "zustand";

import { portfolioApi } from "../services/api/portfolio.api";
import type { HoldingCreate, HoldingUpdate, Portfolio } from "../types/userFeatures";
import { toErrorMessage } from "../utils/apiErrors";
import { toast } from "./toastStore";

/**
 * The signed-in user's portfolio as returned by GET /portfolio — values, P&L and allocation are all
 * calculated by the backend from the user's recorded holdings and the CURRENT synced market prices; this
 * store never computes or invents them. Mutations are followed by a reload so the totals always come from
 * the server. Record-keeping only: nothing here can place an order.
 */
export type PortfolioStatus = "idle" | "loading" | "ready" | "error";

interface PortfolioState {
  userId: string | null;
  portfolio: Portfolio | null;
  status: PortfolioStatus;
  error: string | null;
  saving: boolean;
  /** Error from the last add/update/remove (shown by the form), separate from the load error. */
  actionError: string | null;

  load: (userId: string | null) => Promise<void>;
  reload: () => Promise<void>;
  addHolding: (payload: HoldingCreate) => Promise<boolean>;
  updateHolding: (coinId: string, payload: HoldingUpdate) => Promise<boolean>;
  removeHolding: (coinId: string) => Promise<boolean>;
  clearActionError: () => void;
  reset: () => void;
}

const INITIAL = { userId: null, portfolio: null, status: "idle" as PortfolioStatus, error: null, saving: false, actionError: null };
let seq = 0;

export const usePortfolioStore = create<PortfolioState>((set, get) => ({
  ...INITIAL,

  load: async (userId) => {
    const mine = ++seq;
    if (!userId) {
      set({ ...INITIAL });
      return;
    }
    set({
      userId,
      portfolio: get().userId === userId ? get().portfolio : null,
      status: "loading",
      error: null,
    });
    try {
      const portfolio = await portfolioApi.get();
      if (mine !== seq) return;
      set({ portfolio, status: "ready", error: null });
    } catch (error) {
      if (mine !== seq) return;
      set({ status: "error", error: toErrorMessage(error, "Your portfolio could not be loaded.") });
    }
  },

  reload: async () => {
    const { userId } = get();
    if (userId) await get().load(userId);
  },

  addHolding: async (payload) => run(set, get, () => portfolioApi.add(payload), "Could not save this holding.", "Holding added to your portfolio."),
  updateHolding: async (coinId, payload) =>
    run(set, get, () => portfolioApi.update(coinId, payload), "Could not update this holding.", "Holding updated."),
  removeHolding: async (coinId) =>
    run(set, get, () => portfolioApi.remove(coinId), "Could not remove this holding.", "Holding removed from your portfolio."),

  clearActionError: () => set({ actionError: null }),
  reset: () => {
    seq += 1;
    set({ ...INITIAL });
  },
}));

async function run(
  set: (partial: Partial<PortfolioState>) => void,
  get: () => PortfolioState,
  action: () => Promise<unknown>,
  fallback: string,
  success: string
): Promise<boolean> {
  set({ saving: true, actionError: null });
  try {
    await action();
  } catch (error) {
    set({ saving: false, actionError: toErrorMessage(error, fallback) });
    return false;
  }
  set({ saving: false });
  toast.success(success);
  await get().reload();
  return true;
}
