import { Link, useNavigate } from "react-router-dom";
import { LayoutDashboard, LineChart, LogOut, Moon, Newspaper, Star, Sun, TrendingUp } from "lucide-react";

import { useAuthStore } from "../../store/authStore";
import { useTheme } from "../../context/ThemeContext";
import { CommandPalette } from "../search/CommandPalette";
import { GlobalSearch } from "../search/GlobalSearch";

/**
 * Top navigation used by the authenticated app pages (Dashboard,
 * Markets, Coin Details). Not shown on the landing page or the
 * auth pages themselves.
 */
export function Header() {
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { theme, toggleTheme } = useTheme();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <Link to="/dashboard" className="flex items-center gap-2 font-bold text-slate-900 dark:text-slate-100">
          <TrendingUp className="h-5 w-5 text-sky-500" aria-hidden="true" />
          <span className="hidden sm:inline">Crypto AI Platform</span>
        </Link>

        <nav className="flex items-center gap-1 text-sm font-medium">
          <Link
            to="/dashboard"
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
            Dashboard
          </Link>
          <Link
            to="/markets"
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <LineChart className="h-4 w-4" aria-hidden="true" />
            Markets
          </Link>
          <Link
            to="/news"
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <Newspaper className="h-4 w-4" aria-hidden="true" />
            News
          </Link>
          <Link
            to="/markets?tab=watchlist"
            className="hidden items-center gap-1.5 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 md:flex"
          >
            <Star className="h-4 w-4" aria-hidden="true" />
            Watchlist
          </Link>
        </nav>

        <GlobalSearch />

        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        {isAuthenticated ? (
          <div className="flex items-center gap-2">
            <span className="hidden text-sm font-medium text-slate-700 dark:text-slate-200 sm:inline">
              {user?.name}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 dark:bg-sky-600 dark:hover:bg-sky-500"
          >
            Log in
          </Link>
        )}
      </div>
      {isAuthenticated && <CommandPalette />}
    </header>
  );
}
