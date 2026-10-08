import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./ProtectedRoute";
import { useAuthStore } from "../store/authStore";

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <div>Secret Dashboard Content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
});

describe("ProtectedRoute", () => {
  it("shows a loading state while auth initialization is in flight", () => {
    useAuthStore.setState({ isLoading: true });
    renderProtected();
    expect(screen.getByText(/checking session/i)).toBeInTheDocument();
    expect(screen.queryByText("Secret Dashboard Content")).not.toBeInTheDocument();
  });

  it("redirects to /login when not authenticated", () => {
    useAuthStore.setState({ isLoading: false, isAuthenticated: false });
    renderProtected();
    expect(screen.getByText("Login Page")).toBeInTheDocument();
    expect(screen.queryByText("Secret Dashboard Content")).not.toBeInTheDocument();
  });

  it("renders the protected content when authenticated", () => {
    useAuthStore.setState({
      isLoading: false,
      isAuthenticated: true,
      user: { id: "1", name: "Real User", email: "real@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
    });
    renderProtected();
    expect(screen.getByText("Secret Dashboard Content")).toBeInTheDocument();
  });
});
