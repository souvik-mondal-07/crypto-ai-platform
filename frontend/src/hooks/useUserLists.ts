import { useEffect } from "react";

import { useAuthStore } from "../store/authStore";
import { useUserListsStore } from "../store/userListsStore";

/**
 * Keeps the client-side lists in step with the signed-in user. Mounted once
 * (AppShell), so switching accounts in the same browser swaps lists instead of
 * leaking one user's watchlist to the next.
 */
export function useSyncUserLists(): void {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const load = useUserListsStore((state) => state.load);

  useEffect(() => {
    load(userId);
  }, [userId, load]);
}
