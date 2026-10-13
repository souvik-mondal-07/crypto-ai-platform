import { useCallback, useState, type ReactNode } from "react";

import { useActiveAlertCount } from "../../hooks/useActiveAlertCount";
import { useSyncUserLists } from "../../hooks/useUserLists";
import { useSyncUserData } from "../../hooks/useUserData";
import { ToastViewport } from "../ui/ToastViewport";
import { Header } from "./Header";
import { PageContainer } from "./PageContainer";
import { Sidebar } from "./Sidebar";

interface AppShellProps {
  children: ReactNode;
}

/**
 * Frame for the "real app" pages (Dashboard, Markets, Coin Details, ...): a fixed sidebar from lg (a drawer below),
 * a sticky top bar, and the page content. The content column is offset by the sidebar width and can shrink
 * (min-w-0), so nothing can push the page sideways.
 */
export function AppShell({ children }: AppShellProps) {
  // Keep the per-user watchlist / recently-viewed lists in step with the signed-in user.
  useSyncUserLists();
  // Server-backed watchlist / settings (and a clean slate when the account changes).
  useSyncUserData();

  const [menuOpen, setMenuOpen] = useState(false);
  const openMenu = useCallback(() => setMenuOpen(true), []);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const alertCount = useActiveAlertCount();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[radial-gradient(ellipse_at_top,#101a38_0%,#080d18_55%)] dark:bg-slate-950">
      {/* Keyboard users can jump past the navigation straight to the page content. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-sky-600 focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to main content
      </a>
      <Sidebar mobileOpen={menuOpen} onMobileClose={closeMenu} alertCount={alertCount} />
      <div className="min-w-0 lg:pl-60">
        <Header onOpenMenu={openMenu} menuOpen={menuOpen} alertCount={alertCount} />
        <PageContainer wide>{children}</PageContainer>
      </div>
      <ToastViewport />
    </div>
  );
}
