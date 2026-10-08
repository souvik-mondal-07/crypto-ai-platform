import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { Loader } from "../components/common/Loader";
import { useAuthStore } from "../store/authStore";

interface ProtectedRouteProps {
  children: ReactNode;
}

/**
 * Gates access to authenticated-only pages. Shows a loading state
 * while auth initialization (the startup /auth/me check) is still in
 * flight, so an unauthenticated flash never appears for a user who
 * actually does have a valid stored session.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return <Loader label="Checking session..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
