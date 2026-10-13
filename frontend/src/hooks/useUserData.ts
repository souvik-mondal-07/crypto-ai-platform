import { useEffect } from "react";

import { useOptionalTheme } from "../context/ThemeContext";
import { useAuthStore } from "../store/authStore";
import { usePortfolioStore } from "../store/portfolioStore";
import { useSettingsStore } from "../store/settingsStore";
import { useWatchlistStore } from "../store/watchlistStore";

/** Which user the saved theme was last applied for. Module-level: AppShell remounts on every page change. */
let themeAppliedFor: string | null = null;

/**
 * Keeps the server-backed user data in step with the signed-in account. Mounted by AppShell (so it runs on
 * every app page, but only does work when the signed-in user actually changes).
 *  - Switching/leaving an account clears the previous user's cached watchlist, portfolio and settings
 *    before anything else is shown, so data can never carry over between users in one browser tab.
 *  - A saved theme preference is applied ONCE per sign-in, after settings load; a user who has never
 *    chosen a theme keeps their device's theme.
 */
export function useSyncUserData(): void {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const themeContext = useOptionalTheme();
  const theme = themeContext?.theme;
  const setTheme = themeContext?.setTheme;
  const settingsStatus = useSettingsStore((state) => state.status);
  const savedTheme = useSettingsStore((state) => state.settings.theme);

  useEffect(() => {
    if (usePortfolioStore.getState().userId !== userId) usePortfolioStore.getState().reset();
    const watchlist = useWatchlistStore.getState();
    if (watchlist.userId !== userId || (userId && watchlist.status === "idle")) void watchlist.load(userId);
    const settings = useSettingsStore.getState();
    if (settings.userId !== userId || (userId && settings.status === "idle")) void settings.load(userId);
    if (!userId) themeAppliedFor = null;
  }, [userId]);

  useEffect(() => {
    if (!userId || !setTheme || settingsStatus !== "ready" || themeAppliedFor === userId) return;
    themeAppliedFor = userId;
    if (savedTheme && savedTheme !== theme) setTheme(savedTheme);
  }, [userId, settingsStatus, savedTheme, theme, setTheme]);
}
