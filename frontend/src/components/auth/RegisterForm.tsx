import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, Loader2 } from "lucide-react";

import { ErrorMessage } from "../common/ErrorMessage";
import { PasswordField, TextField } from "../common/FormFields";
import { useAuthStore } from "../../store/authStore";

const MIN_PASSWORD_LENGTH = 8;

export function RegisterForm() {
  const navigate = useNavigate();
  const { register, isLoading, error, clearError } = useAuthStore();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [succeeded, setSucceeded] = useState(false);

  function validate(): string | null {
    if (!name.trim()) return "Enter your name.";
    if (!email.trim()) return "Enter your email.";
    if (password.length < MIN_PASSWORD_LENGTH) {
      return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (password !== confirmPassword) return "Passwords do not match.";
    return null;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (isLoading) return; // prevent duplicate submissions

    clearError();
    const validation = validate();
    setValidationError(validation);
    if (validation) return;

    try {
      // V1 behavior: registration does NOT log the user in
      // automatically — it redirects to /login so they authenticate
      // normally (see docs/authentication.md).
      await register(name.trim(), email.trim(), password, confirmPassword);
      setSucceeded(true);
      setTimeout(() => navigate("/login"), 1200);
    } catch {
      // authStore already captured the error message in its `error` state.
    }
  }

  const displayedError = validationError || error;

  if (succeeded) {
    return (
      <div className="flex flex-col items-center gap-2 py-4 text-center">
        <CheckCircle2 className="h-8 w-8 text-emerald-500" aria-hidden="true" />
        <p className="text-sm font-medium text-slate-800 dark:text-slate-100">Account created.</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">Redirecting you to login...</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="space-y-4">
        <TextField
          id="register-name"
          label="Name"
          type="text"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isLoading}
          hasError={Boolean(displayedError)}
        />

        <TextField
          id="register-email"
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={isLoading}
          hasError={Boolean(displayedError)}
        />

        <PasswordField
          id="register-password"
          label="Password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isLoading}
          hasError={Boolean(displayedError)}
        />

        <PasswordField
          id="register-confirm-password"
          label="Confirm Password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
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
          {isLoading ? "Registering..." : "Create Account"}
        </button>
      </div>

      <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-sky-600 hover:underline dark:text-sky-400">
          Login
        </Link>
      </p>
    </form>
  );
}
