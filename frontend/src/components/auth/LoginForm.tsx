import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { ErrorMessage } from "../common/ErrorMessage";
import { PasswordField, TextField } from "../common/FormFields";
import { useAuthStore } from "../../store/authStore";

export function LoginForm() {
  const navigate = useNavigate();
  const { login, isLoading, error, clearError } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (isLoading) return; // prevent duplicate submissions while a request is in flight

    setValidationError(null);
    clearError();

    if (!email.trim() || !password) {
      setValidationError("Enter your email and password.");
      return;
    }

    try {
      await login(email.trim(), password);
      navigate("/dashboard");
    } catch {
      // authStore already captured the error message in its `error` state.
    }
  }

  const displayedError = validationError || error;

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="space-y-4">
        <TextField
          id="login-email"
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={isLoading}
          hasError={Boolean(displayedError)}
        />

        <PasswordField
          id="login-password"
          label="Password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isLoading}
          hasError={Boolean(displayedError)}
        />

        {displayedError && <ErrorMessage message={displayedError} />}

        <button
          type="submit"
          disabled={isLoading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-sky-600 dark:hover:bg-sky-500"
        >
          {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {isLoading ? "Logging in..." : "Login"}
        </button>
      </div>

      <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
        Don't have an account?{" "}
        <Link to="/register" className="font-medium text-sky-600 hover:underline dark:text-sky-400">
          Create account
        </Link>
      </p>
    </form>
  );
}
