import { useEffect } from "react";

import { useAuthStore } from "../store/authStore";
import { usePortfolioStore } from "../store/portfolioStore";

/** Loads the signed-in user's portfolio when the page mounts (so prices are fresh on every visit). */
export function usePortfolio() {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const store = usePortfolioStore();
  const { load } = store;

  useEffect(() => {
    void load(userId);
  }, [userId, load]);

  return store;
}
