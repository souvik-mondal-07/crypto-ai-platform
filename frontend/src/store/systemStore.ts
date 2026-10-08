import { create } from "zustand";

import { fetchHealth } from "../services/api/health.service";
import type { BackendStatus } from "../types/health.types";

interface SystemState {
  backendStatus: BackendStatus;
  errorMessage: string | null;
  checkBackendHealth: () => Promise<void>;
}

/**
 * Minimal application/system status store for Step 1.
 * Feature-specific stores (auth, market, prediction, portfolio, ...)
 * will be introduced in later steps — do not add them here yet.
 */
export const useSystemStore = create<SystemState>((set) => ({
  backendStatus: "checking",
  errorMessage: null,

  checkBackendHealth: async () => {
    set({ backendStatus: "checking", errorMessage: null });
    try {
      await fetchHealth();
      set({ backendStatus: "online", errorMessage: null });
    } catch (error) {
      set({
        backendStatus: "offline",
        errorMessage: error instanceof Error ? error.message : "Backend unavailable.",
      });
    }
  },
}));
