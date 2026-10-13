import { create } from "zustand";

import { settingsApi } from "../services/api/settings.api";
import type { UserSettings, UserSettingsUpdate } from "../types/userFeatures";
import { toErrorMessage } from "../utils/apiErrors";
import { toast } from "./toastStore";

/**
 * The signed-in user's saved preferences (GET/PUT /settings), stored on the user's own record.
 * The light/dark mechanism itself stays in ThemeContext (the single theme system); this store only
 * remembers the user's CHOICE so it follows them across devices. `theme: null` means "never chosen" —
 * the device's own theme is then left alone.
 */
export type SettingsStatus = "idle" | "loading" | "ready" | "error";

export const DEFAULT_SETTINGS: UserSettings = { theme: null, notifications: { price_alerts: true } };

interface SettingsState {
  userId: string | null;
  settings: UserSettings;
  status: SettingsStatus;
  error: string | null;
  saving: boolean;
  saveError: string | null;

  load: (userId: string | null) => Promise<void>;
  update: (changes: UserSettingsUpdate) => Promise<boolean>;
  reset: () => void;
}

const INITIAL = { userId: null, settings: DEFAULT_SETTINGS, status: "idle" as SettingsStatus, error: null, saving: false, saveError: null };
let seq = 0;

export const useSettingsStore = create<SettingsState>((set, get) => ({
  ...INITIAL,

  load: async (userId) => {
    const mine = ++seq;
    if (!userId) {
      set({ ...INITIAL });
      return;
    }
    set({ userId, status: "loading", error: null, settings: get().userId === userId ? get().settings : DEFAULT_SETTINGS });
    try {
      const settings = await settingsApi.get();
      if (mine !== seq) return;
      set({ settings, status: "ready", error: null });
    } catch (error) {
      if (mine !== seq) return;
      set({ status: "error", error: toErrorMessage(error, "Your settings could not be loaded.") });
    }
  },

  update: async (changes) => {
    const previous = get().settings;
    // Optimistic, so toggles feel instant; rolled back if the server refuses.
    set({
      saving: true,
      saveError: null,
      settings: {
        theme: "theme" in changes ? (changes.theme ?? null) : previous.theme,
        notifications: { ...previous.notifications, ...(changes.notifications ?? {}) } as UserSettings["notifications"],
      },
    });
    try {
      const saved = await settingsApi.update(changes);
      set({ settings: saved, saving: false });
      toast.success("Settings saved.");
      return true;
    } catch (error) {
      set({ settings: previous, saving: false, saveError: toErrorMessage(error, "Your settings could not be saved.") });
      return false;
    }
  },

  reset: () => {
    seq += 1;
    set({ ...INITIAL });
  },
}));
