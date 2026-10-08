import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { LoginForm } from "./LoginForm";
import { useAuthStore } from "../../store/authStore";
import { authApi } from "../../services/api/auth.api";

vi.mock("../../services/api/auth.api", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}));

const mockedAuthApi = vi.mocked(authApi);

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
});

function renderLoginForm() {
  return render(
    <MemoryRouter>
      <LoginForm />
    </MemoryRouter>
  );
}

describe("LoginForm", () => {
  it("shows a validation message and does not call the API for empty fields", async () => {
    const user = userEvent.setup();
    renderLoginForm();

    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(await screen.findByText(/enter your email and password/i)).toBeInTheDocument();
    expect(mockedAuthApi.login).not.toHaveBeenCalled();
  });

  it("submits valid input and shows a loading state", async () => {
    const user = userEvent.setup();
    let resolveLogin: () => void = () => {};
    mockedAuthApi.login.mockReturnValue(
      new Promise((resolve) => {
        resolveLogin = () =>
          resolve({
            user: { id: "1", name: "X", email: "x@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
            token: { access_token: "t", token_type: "bearer", expires_in_minutes: 60 },
          });
      })
    );
    mockedAuthApi.me.mockResolvedValue({
      id: "1", name: "X", email: "x@example.com", role: "user", created_at: "2026-01-01T00:00:00Z",
    });

    renderLoginForm();
    await user.type(screen.getByLabelText("Email"), "real@example.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(screen.getByText(/logging in/i)).toBeInTheDocument();
    resolveLogin();
    await waitFor(() => expect(mockedAuthApi.login).toHaveBeenCalledWith({ email: "real@example.com", password: "password123" }));
  });

  it("displays the backend's error message on failed login", async () => {
    const user = userEvent.setup();
    mockedAuthApi.login.mockRejectedValue(new Error("Invalid email or password."));

    renderLoginForm();
    await user.type(screen.getByLabelText("Email"), "wrong@example.com");
    await user.type(screen.getByLabelText("Password"), "wrongpass");
    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(await screen.findByText("Invalid email or password.")).toBeInTheDocument();
  });
});
