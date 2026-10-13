import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Bell, ChevronDown, LogOut, Menu, Moon, Settings as SettingsIcon, Sun, User as UserIcon } from "lucide-react";

import { useAuthStore } from "../../store/authStore";
import { useThemePreference } from "../../hooks/useThemePreference";
import { CommandPalette } from "../search/CommandPalette";
import { GlobalSearch } from "../search/GlobalSearch";
import { BrandMark } from "./BrandMark";

const ICON_BUTTON =
  "relative inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:text-slate-300 dark:hover:bg-white/[0.06] dark:hover:text-white";
const MENU_ITEM =
  "flex min-h-[40px] w-full items-center gap-2.5 rounded-lg px-3 text-left text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:text-slate-200 dark:hover:bg-white/[0.06]";

function initials(name: string | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return ((parts[0][0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] ?? "" : "")).toUpperCase();
}

function roleLabel(role: string | undefined): string {
  if (!role) return "Member";
  return role.charAt(0).toUpperCase() + role.slice(1).toLowerCase();
}

interface HeaderProps {
  /** Opens the sidebar drawer (below lg, where the sidebar is hidden). Omit and the menu button is not rendered. */
  onOpenMenu?: () => void;
  menuOpen?: boolean;
  /** Active price alerts, shown as a badge on the bell. */
  alertCount?: number;
}

/**
 * Top bar for the authenticated app pages. Navigation lives in the Sidebar; this holds search, alerts,
 * the theme toggle and the profile menu.
 *
 * Layout (flex only — nothing is absolutely positioned except the profile dropdown panel, which is anchored to
 * its own trigger), so the controls can never collide:
 *   lg and up   one row:  [search (flexes, min-w-0, max 36rem)] .......... [bell] [theme] [profile]
 *   below lg    row 1: [menu] [logo] .......... [bell] [theme] [profile]      row 2: [search, full width]
 * The profile name/role hide below md and the name truncates, so the right-hand group has a small fixed minimum.
 */
export function Header({ onOpenMenu, menuOpen = false, alertCount = 0 }: HeaderProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { theme, toggle: toggleTheme } = useThemePreference();
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setProfileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!profileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setProfileOpen(false);
    };
    const onPointerDown = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) setProfileOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [profileOpen]);

  async function handleLogout() {
    setProfileOpen(false);
    await logout();
    navigate("/login");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-brand-500/15 dark:bg-slate-950/85">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2 px-4 py-3 sm:px-6 lg:flex-nowrap lg:gap-x-4 lg:px-8">
        {onOpenMenu && (
          <button
            type="button"
            onClick={onOpenMenu}
            aria-label="Open menu"
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            title="Menu"
            className={`${ICON_BUTTON} lg:hidden`}
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
        )}

        <Link to="/dashboard" className="flex flex-shrink-0 items-center gap-2 rounded-lg lg:hidden" aria-label="Crypto AI Platform home">
          <BrandMark className="h-8 w-8" />
          <span className="hidden text-sm font-bold text-slate-900 dark:text-white sm:inline">Crypto AI Platform</span>
        </Link>

        {/* Search: its own full-width row below lg; the flexible first item from lg (min-w-0 so it shrinks, never overlaps). */}
        <div className="order-last flex w-full min-w-0 items-center gap-2 lg:order-none lg:w-auto lg:max-w-xl lg:flex-1 lg:basis-0">
          <div className="min-w-0 flex-1">
            <GlobalSearch />
          </div>
          {isAuthenticated && (
            <kbd
              aria-hidden="true"
              className="hidden flex-shrink-0 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-sans text-[11px] font-medium text-slate-500 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-400 md:inline-block"
            >
              Ctrl K
            </kbd>
          )}
        </div>

        <div className="ml-auto flex flex-shrink-0 items-center gap-1 sm:gap-1.5">
          {isAuthenticated && (
            <Link to="/alerts" aria-label={alertCount > 0 ? `Alert notifications (${alertCount} active)` : "Alert notifications"} title="Alerts" className={ICON_BUTTON}>
              <Bell className="h-[18px] w-[18px]" aria-hidden="true" />
              {alertCount > 0 && (
                <span aria-hidden="true" className="absolute -right-0.5 -top-0.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold leading-none text-white">
                  {alertCount > 99 ? "99+" : alertCount}
                </span>
              )}
            </Link>
          )}

          <button type="button" onClick={toggleTheme} aria-label="Toggle theme" title="Toggle theme" className={ICON_BUTTON}>
            {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
          </button>

          {isAuthenticated ? (
            <div ref={profileRef} className="relative">
              <button
                type="button"
                onClick={() => setProfileOpen((open) => !open)}
                aria-haspopup="menu"
                aria-expanded={profileOpen}
                aria-label="Account menu"
                className="flex h-10 items-center gap-2 rounded-xl px-1.5 transition-colors hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:hover:bg-white/[0.06] sm:pr-2"
              >
                <span aria-hidden="true" className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-violet text-xs font-semibold text-white">
                  {initials(user?.name)}
                </span>
                <span className="hidden min-w-0 text-left leading-tight md:block">
                  <span className="block max-w-[8rem] truncate text-sm font-semibold text-slate-900 dark:text-white xl:max-w-[11rem]">{user?.name}</span>
                  <span className="block text-[11px] text-brand-500 dark:text-brand-400">{roleLabel(user?.role)}</span>
                </span>
                <ChevronDown className="hidden h-4 w-4 flex-shrink-0 text-slate-400 md:block" aria-hidden="true" />
              </button>

              {profileOpen && (
                <div
                  role="menu"
                  aria-label="Account menu"
                  className="absolute right-0 top-full z-50 mt-2 w-56 max-w-[calc(100vw-2rem)] rounded-xl border border-slate-200 bg-white p-1.5 shadow-pop animate-fade-in dark:border-brand-500/25 dark:bg-slate-900 motion-reduce:animate-none"
                >
                  <div className="px-3 py-2 md:hidden">
                    <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{user?.name}</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">{roleLabel(user?.role)}</p>
                  </div>
                  <Link to="/profile" role="menuitem" className={MENU_ITEM}>
                    <UserIcon className="h-4 w-4" aria-hidden="true" />
                    Profile
                  </Link>
                  <Link to="/settings" role="menuitem" className={MENU_ITEM}>
                    <SettingsIcon className="h-4 w-4" aria-hidden="true" />
                    Settings
                  </Link>
                  <div className="my-1 border-t border-slate-200 dark:border-white/[0.08]" role="separator" />
                  <button type="button" role="menuitem" onClick={handleLogout} className={MENU_ITEM}>
                    <LogOut className="h-4 w-4" aria-hidden="true" />
                    Logout
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to="/login" className="btn-primary">
              Log in
            </Link>
          )}
        </div>
      </div>
      {isAuthenticated && <CommandPalette />}
    </header>
  );
}
