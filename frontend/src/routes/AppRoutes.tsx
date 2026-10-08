import { Route, Routes } from "react-router-dom";

import { CoinDetails, Dashboard, Home, Login, MarketTest, Markets, News, NotFound, Register } from "../pages";
import { ProtectedRoute } from "./ProtectedRoute";

/**
 * /market-test (Step 3) remains a development-only verification page.
 * /dashboard, /markets, /news (Phase 12) and /coins/:coinId (Step 5) are the "real app"
 * pages and require authentication, consistent with how Step 4
 * protected /dashboard. The landing page (/), /login, and /register
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
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
