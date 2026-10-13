import { useEffect, useRef } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { ArrowRight, Settings as SettingsIcon, Sparkles, X } from "lucide-react";

import { BrandMark } from "./BrandMark";
import { NAV_ITEMS } from "./navigation";

const LINK =
  "group relative flex min-h-[44px] items-center gap-3 rounded-xl px-3 text-sm font-medium text-slate-600 transition-colors duration-200 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/[0.04] dark:hover:text-slate-100";
const LINK_ACTIVE =
  "!text-slate-900 bg-slate-100 dark:!text-white dark:bg-gradient-to-r dark:from-brand-500 dark:to-brand-violet dark:shadow-glow";

function Links({ onNavigate, alertCount = 0 }: { onNavigate?: () => void; alertCount?: number }) {
  return (
    <>
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          aria-label={to === "/alerts" && alertCount > 0 ? `${label} (${alertCount} active)` : undefined}
          className={({ isActive }) => `${LINK} ${isActive ? LINK_ACTIVE : ""}`}
        >
          {({ isActive }) => (
            <>
              {/* Active indicator: a glowing bar on the leading edge. */}
              <span
                aria-hidden="true"
                className={`absolute -left-3 top-2 bottom-2 w-1 rounded-full bg-gradient-to-b from-brand-cyan to-brand-violet transition-opacity duration-200 ${isActive ? "opacity-100" : "opacity-0"}`}
              />
              <Icon className="h-[18px] w-[18px] flex-shrink-0" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">{label}</span>
              {to === "/alerts" && alertCount > 0 && (
                <span aria-hidden="true" className="ml-auto inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-rose-500 px-1.5 text-[11px] font-semibold leading-none text-white">
                  {alertCount > 99 ? "99+" : alertCount}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </>
  );
}

function SidebarBody({ onNavigate, onClose, alertCount }: { onNavigate?: () => void; onClose?: () => void; alertCount?: number }) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between px-5 pb-4 pt-5">
        <Link to="/dashboard" onClick={onNavigate} className="flex items-center gap-2.5 rounded-lg">
          <BrandMark className="h-9 w-9" />
          <span className="leading-tight">
            <span className="block text-[15px] font-bold tracking-tight text-slate-900 dark:text-white">Crypto AI</span>
            <span className="block text-xs font-medium text-brand-500 dark:text-brand-400">Platform</span>
          </span>
        </Link>
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Close menu" className="btn-icon">
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        )}
      </div>

      <nav aria-label={onClose ? "Mobile" : "Main"} className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        <Links onNavigate={onNavigate} alertCount={alertCount} />
      </nav>

      <div className="space-y-3 px-3 pb-4">
        <div className="border-t border-slate-200 pt-3 dark:border-white/[0.07]">
          <NavLink to="/settings" onClick={onNavigate} className={({ isActive }) => `${LINK} ${isActive ? LINK_ACTIVE : ""}`}>
            <SettingsIcon className="h-[18px] w-[18px]" aria-hidden="true" />
            Settings
          </NavLink>
        </div>

        <div className="ai-surface p-4">
          <div aria-hidden="true" className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 animate-glow rounded-full bg-brand-violet/30 blur-2xl motion-reduce:animate-none" />
          <p className="relative flex items-center gap-1.5 text-sm font-semibold text-slate-900 dark:text-white">
            <Sparkles className="h-4 w-4 text-brand-violet" aria-hidden="true" />
            Powered by Gemini AI
          </p>
          <p className="relative mt-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
            Get intelligent market insights, analysis and context for every coin.
          </p>
          <Link to="/markets" onClick={onNavigate} className="btn-gradient relative mt-3 w-full !min-h-[2rem] !py-1 text-xs">
            Explore AI Analysis
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </div>
  );
}

interface SidebarProps {
  mobileOpen: boolean;
  onMobileClose: () => void;
  /** Number of the user's active price alerts (badge on the Alerts link); omitted/0 hides it. */
  alertCount?: number;
}

/**
 * Application sidebar. Fixed on the left from lg; below lg it is an accessible slide-in drawer
 * (labelled dialog, Escape / scrim / route change close it, focus moves in on open and back to the menu button).
 */
export function Sidebar({ mobileOpen, onMobileClose, alertCount = 0 }: SidebarProps) {
  const location = useLocation();
  const drawerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    onMobileClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const opener = document.activeElement as HTMLElement | null;
    drawerRef.current?.querySelector<HTMLElement>("a, button")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onMobileClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      opener?.focus?.();
    };
  }, [mobileOpen, onMobileClose]);

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-slate-200 bg-white/80 backdrop-blur-xl dark:border-brand-500/15 dark:bg-gradient-to-b dark:from-slate-950 dark:via-slate-950 dark:to-[#120d2e] lg:block">
        <SidebarBody alertCount={alertCount} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button type="button" aria-label="Close menu overlay" tabIndex={-1} onClick={onMobileClose} className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm animate-fade-in motion-reduce:animate-none" />
          <div
            ref={drawerRef}
            id="mobile-menu"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-slate-200 bg-white shadow-pop animate-fade-in dark:border-white/[0.07] dark:bg-slate-950 motion-reduce:animate-none"
          >
            <SidebarBody onNavigate={onMobileClose} onClose={onMobileClose} alertCount={alertCount} />
          </div>
        </div>
      )}
    </>
  );
}
