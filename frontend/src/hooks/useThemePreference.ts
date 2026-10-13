import { useCallback } from "react";

import { useTheme, type Theme } from "../context/ThemeContext";
import { useAuthStore } from "../store/authStore";
import { useSettingsStore } from "../store/settingsStore";

/**
 * The ONE place a theme change is made by the user: ThemeContext still owns light/dark (and its
 * localStorage fallback); when signed in the choice is also saved to the account so it follows the user.
 */
export function useThemePreference() {
  const { theme, setTheme } = useTheme();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const choose = useCallback(
    (next: Theme) => {
      setTheme(next);
      if (isAuthenticated) void useSettingsStore.getState().update({ theme: next });
    },
    [setTheme, isAuthenticated]
  );
  const toggle = useCallback(() => choose(theme === "dark" ? "light" : "dark"), [choose, theme]);
  return { theme, choose, toggle };
}
