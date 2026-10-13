import { Route, Routes } from "react-router-dom";

import {
  Alerts,
  CoinDetails,
  Dashboard,
  History,
  Home,
  Login,
  MarketTest,
  Markets,
  News,
  NotFound,
  Portfolio,
  Profile,
  Register,
  Settings,
  Watchlist,
} from "../pages";
import { ProtectedRoute } from "./ProtectedRoute";

/**
 * /market-test (Step 3) remains a development-only verification page.
 * /dashboard, /markets, /news (Phase 12) and /coins/:coinId (Step 5) are the "real app"
 * pages and require authentication, consistent with how Step 4
 * protected /dashboard. Phase 16's user-feature pages (/watchlist, /portfolio,
 * /history, /alerts, /profile, /settings) are protected the same way. The landing page (/), /login, and /register
 * remain public.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/market-test" element={<MarketTest />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/markets"
        element={
          <ProtectedRoute>
            <Markets />
          </ProtectedRoute>
        }
      />
      <Route
        path="/coins/:coinId"
        element={
          <ProtectedRoute>
            <CoinDetails />
          </ProtectedRoute>
        }
      />
      <Route
        path="/news"
        element={
          <ProtectedRoute>
            <News />
          </ProtectedRoute>
        }
      />
      <Route
        path="/watchlist"
        element={
          <ProtectedRoute>
            <Watchlist />
          </ProtectedRoute>
        }
      />
      <Route
        path="/portfolio"
        element={
          <ProtectedRoute>
            <Portfolio />
          </ProtectedRoute>
        }
      />
      <Route
        path="/history"
        element={
          <ProtectedRoute>
            <History />
          </ProtectedRoute>
        }
      />
      <Route
        path="/alerts"
        element={
          <ProtectedRoute>
            <Alerts />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
