import type { ReactNode } from "react";

import { useSyncUserLists } from "../../hooks/useUserLists";
import { Header } from "./Header";
import { PageContainer } from "./PageContainer";

interface AppShellProps {
  children: ReactNode;
}

/** Used by Dashboard, Markets, and Coin Details — the "real app" pages, as opposed to the landing/auth pages. */
export function AppShell({ children }: AppShellProps) {
  // Keep the per-user watchlist / recently-viewed lists in step with the signed-in user.
  useSyncUserLists();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Header />
      <PageContainer wide>{children}</PageContainer>
    </div>
  );
}
