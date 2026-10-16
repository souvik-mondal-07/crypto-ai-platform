import { BarChart3, Bell, FlaskConical, History as HistoryIcon, LayoutDashboard, Newspaper, Star, Wallet, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

/**
 * The single list of primary destinations, used by the sidebar (desktop) and its drawer (mobile).
 * Only REAL routes appear here: technical/fundamental analysis, predictions, risk and AI analysis are sections
 * of each coin's page (reached from Markets or search), not standalone pages, so they are not faked as links.
 */
export const NAV_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/markets", label: "Markets", icon: BarChart3 },
  { to: "/portfolio", label: "Portfolio", icon: Wallet },
  { to: "/watchlist", label: "Watchlist", icon: Star },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/news", label: "News & Sentiment", icon: Newspaper },
  { to: "/history", label: "History", icon: HistoryIcon },
  { to: "/backtesting", label: "Backtesting & Accuracy", icon: FlaskConical },
];
