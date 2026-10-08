import { forwardRef, useId, useState, type InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";

/**
 * Shared form input.
 *
 * ROOT CAUSE THIS FIXES: the auth forms previously used a bare
 * `<input>` with no `text-*` or `bg-*` class. Tailwind's preflight
 * doesn't give inputs a background, so they fell back to the
 * browser default (white) while inheriting `color` from `body`,
 * which is `dark:text-slate-100` in dark mode. The result was
 * near-white password dots on a white field — invisible.
 *
 * Every input now sets BOTH its background and its text color
 * explicitly in each theme, so the contrast never depends on
 * inherited body color. Autofill is handled in index.css, since
 * browsers override background/color on autofilled fields in a way
 * utility classes can't reach.
 */

const BASE_INPUT_CLASSES =
  "w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors " +
  "bg-white text-slate-900 placeholder:text-slate-400 " +
  "border-slate-300 " +
  "focus:border-sky-500 focus:ring-1 focus:ring-sky-500 " +
  "disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 " +
  "dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 " +
  "dark:border-slate-700 dark:focus:border-sky-400 dark:focus:ring-sky-400 " +
  "dark:disabled:bg-slate-800 dark:disabled:text-slate-400";

const ERROR_CLASSES = "border-red-500 focus:border-red-500 focus:ring-red-500 dark:border-red-500";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hasError?: boolean;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hasError = false, id, className, ...inputProps },
  ref
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div>
      <label
        htmlFor={inputId}
        className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200"
      >
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        className={`${BASE_INPUT_CLASSES} ${hasError ? ERROR_CLASSES : ""} ${className ?? ""}`}
        aria-invalid={hasError || undefined}
        {...inputProps}
      />
    </div>
  );
});

interface PasswordFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  hasError?: boolean;
}

/**
 * Password input with a show/hide toggle. Masking stays on by
 * default — the toggle is opt-in per field and resets on unmount.
 * Both the masked dots and the revealed text use the same explicit
 * colors as TextField, so both are clearly visible in either theme.
 */
export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(function PasswordField(
  { label, hasError = false, id, className, disabled, ...inputProps },
  ref
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const [revealed, setRevealed] = useState(false);

  return (
    <div>
      <label
        htmlFor={inputId}
        className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200"
      >
        {label}
      </label>
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          type={revealed ? "text" : "password"}
          disabled={disabled}
          className={`${BASE_INPUT_CLASSES} pr-10 ${hasError ? ERROR_CLASSES : ""} ${className ?? ""}`}
          aria-invalid={hasError || undefined}
          {...inputProps}
        />
        <button
          type="button"
          onClick={() => setRevealed((current) => !current)}
          disabled={disabled}
          aria-label={revealed ? "Hide password" : "Show password"}
          aria-pressed={revealed}
          className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 hover:text-slate-600 disabled:cursor-not-allowed dark:text-slate-500 dark:hover:text-slate-300"
        >
          {revealed ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
    </div>
  );
});
