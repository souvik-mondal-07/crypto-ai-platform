import { create } from "zustand";

import { watchlistApi } from "../services/api/watchlist.api";
import { ApiError } from "../types/apiError";
import { toErrorMessage } from "../utils/apiErrors";
import { toast } from "./toastStore";

/**
 * The signed-in user's watchlist, held as the set of watched coin ids.
 *
 * The SERVER is the source of truth (GET/POST/DELETE /watchlist, scoped to the JWT's user). This store only
 * caches the ids so stars render instantly everywhere. Changes are optimistic and are rolled back if the
 * server rejects them; the market data shown on the Watchlist page is always read live from the backend,
 * never stored here. `load(userId)` is called whenever the signed-in user changes, so one account's list is
 * never shown to the next.
 */
export type WatchlistStatus = "idle" | "loading" | "ready" | "error";
export interface WatchlistNotice {
  kind: "success" | "info" | "error";
  message: string;
}

interface WatchlistState {
  userId: string | null;
  ids: string[];
  status: WatchlistStatus;
  error: string | null;
  notice: WatchlistNotice | null;
  /** Coin ids with a request in flight (disables their star so a double click can't race). */
  pending: string[];

  load: (userId: string | null) => Promise<void>;
  add: (coinId: string, name?: string) => Promise<void>;
  remove: (coinId: string, name?: string) => Promise<void>;
  toggle: (coinId: string, name?: string) => Promise<void>;
  clearNotice: () => void;
  reset: () => void;
}

const INITIAL = { userId: null, ids: [], status: "idle" as WatchlistStatus, error: null, notice: null, pending: [] };
let loadSeq = 0;

export const useWatchlistStore = create<WatchlistState>((set, get) => ({
  ...INITIAL,

  load: async (userId) => {
    const seq = ++loadSeq;
    if (!userId) {
      set({ ...INITIAL });
      return;
    }
    // Different user => drop the previous user's ids immediately, before anything is fetched.
    set({ userId, ids: get().userId === userId ? get().ids : [], status: "loading", error: null });
    try {
      const response = await watchlistApi.list(1, 250);
      if (seq !== loadSeq) return; // a newer load (or a logout) superseded this one
      set({ ids: response.items.map((item) => item.coin_id), status: "ready", error: null });
    } catch (error) {
      if (seq !== loadSeq) return;
      set({ status: "error", error: toErrorMessage(error, "Your watchlist could not be loaded.") });
    }
  },

  add: async (coinId, name) => {
    const label = name ?? "Coin";
    if (get().pending.includes(coinId)) return;
    const had = get().ids.includes(coinId);
    set({ pending: [...get().pending, coinId], ids: had ? get().ids : [coinId, ...get().ids], notice: null });
    try {
      await watchlistApi.add(coinId);
      set({ notice: { kind: "success", message: `${label} added to your watchlist.` } });
    } catch (error) {
      if (error instanceof ApiError && error.code === "WATCHLIST_ALREADY_EXISTS") {
        set({ notice: { kind: "info", message: `${label} is already in your watchlist.` } });
      } else {
        set({
          ids: had ? get().ids : get().ids.filter((id) => id !== coinId),
          notice: {
            kind: "error",
            message:
              error instanceof ApiError && error.code === "COIN_NOT_FOUND"
                ? "That coin could not be found."
                : toErrorMessage(error, "Could not add to your watchlist."),
          },
        });
      }
    } finally {
      set({ pending: get().pending.filter((id) => id !== coinId) });
    }
  },

  remove: async (coinId, name) => {
    const label = name ?? "Coin";
    if (get().pending.includes(coinId)) return;
    const had = get().ids.includes(coinId);
    set({ pending: [...get().pending, coinId], ids: get().ids.filter((id) => id !== coinId), notice: null });
    try {
      await watchlistApi.remove(coinId);
      set({ notice: { kind: "success", message: `${label} removed from your watchlist.` } });
    } catch (error) {
      if (error instanceof ApiError && error.code === "WATCHLIST_ENTRY_NOT_FOUND") {
        set({ notice: { kind: "info", message: `${label} was already removed.` } });
      } else {
        set({
          ids: had && !get().ids.includes(coinId) ? [coinId, ...get().ids] : get().ids,
          notice: { kind: "error", message: toErrorMessage(error, "Could not remove from your watchlist.") },
        });
      }
    } finally {
      set({ pending: get().pending.filter((id) => id !== coinId) });
    }
  },

  toggle: async (coinId, name) => {
    if (get().ids.includes(coinId)) await get().remove(coinId, name);
    else await get().add(coinId, name);
  },

  clearNotice: () => set({ notice: null }),
  reset: () => {
    loadSeq += 1;
    set({ ...INITIAL });
  },
}));

// Every watchlist outcome (added / already there / removed / failed) is announced as a toast, wherever the
// action was taken (Markets table, Coin Details, Watchlist page). `notice` stays in the store for consumers/tests.
useWatchlistStore.subscribe((state, previous) => {
  if (state.notice && state.notice !== previous.notice) toast[state.notice.kind](state.notice.message);
});
