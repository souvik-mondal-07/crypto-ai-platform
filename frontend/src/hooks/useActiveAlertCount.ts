import { useEffect } from "react";

import { useAlertBadgeStore } from "../store/alertBadgeStore";
import { useAuthStore } from "../store/authStore";

/** The active-alert count to badge for the CURRENT user (0 when signed out or when the count belongs to another account). */
export function useActiveAlertCount(): number {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const badgeUserId = useAlertBadgeStore((state) => state.userId);
  const count = useAlertBadgeStore((state) => state.count);
  return userId && badgeUserId === userId ? count : 0;
}

/** Loads (and refreshes on account change) the active-alert count. Called by the Dashboard, the app's landing page. */
export function useLoadActiveAlertCount(): void {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const load = useAlertBadgeStore((state) => state.load);
  useEffect(() => {
    void load(userId);
  }, [userId, load]);
}
