import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
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
  "w-full rounded-xl border px-3.5 py-2.5 text-sm outline-none transition duration-200 " +
  "bg-white text-slate-900 placeholder:text-slate-400 " +
  "border-slate-300 " +
  "focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 " +
  "disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 " +
  "dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 " +
  "dark:border-white/10 dark:focus:border-brand-400 dark:focus:ring-brand-400/30 " +
  "dark:disabled:bg-slate-800 dark:disabled:text-slate-400";

const ERROR_CLASSES = "border-red-500 focus:border-red-500 focus:ring-red-500/30 dark:border-red-500/70";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hasError?: boolean;
  /** Decorative icon shown inside the field's left edge. */
  leadingIcon?: ReactNode;
  /** Inline validation message shown (and announced) directly under the field. */
  error?: string | null;
}

const LABEL = "mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-200";

function FieldError({ id, message }: { id: string; message: string | null | undefined }) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-red-600 animate-fade-in motion-reduce:animate-none dark:text-red-400">
      {message}
    </p>
  );
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hasError = false, leadingIcon, error, id, className, ...inputProps },
  ref
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;
  const invalid = hasError || Boolean(error);

  return (
    <div>
      <label htmlFor={inputId} className={LABEL}>
        {label}
      </label>
      <div className="relative">
        {leadingIcon && (
          <span className="pointer-events-none absolute inset-y-0 left-0 flex w-11 items-center justify-center text-slate-400 dark:text-slate-500" aria-hidden="true">
            {leadingIcon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`${BASE_INPUT_CLASSES} ${leadingIcon ? "pl-11" : ""} ${invalid ? ERROR_CLASSES : ""} ${className ?? ""}`}
          aria-invalid={invalid || undefined}
          aria-describedby={error ? errorId : undefined}
          {...inputProps}
        />
      </div>
      <FieldError id={errorId} message={error} />
    </div>
  );
});

interface PasswordFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  hasError?: boolean;
  leadingIcon?: ReactNode;
  error?: string | null;
}

/**
 * Password input with a show/hide toggle. Masking stays on by
 * default — the toggle is opt-in per field and resets on unmount.
 * Both the masked dots and the revealed text use the same explicit
 * colors as TextField, so both are clearly visible in either theme.
 */
export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(function PasswordField(
  { label, hasError = false, leadingIcon, error, id, className, disabled, ...inputProps },
  ref
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;
  const invalid = hasError || Boolean(error);
  const [revealed, setRevealed] = useState(false);

  return (
    <div>
      <label htmlFor={inputId} className={LABEL}>
        {label}
      </label>
      <div className="relative">
        {leadingIcon && (
          <span className="pointer-events-none absolute inset-y-0 left-0 flex w-11 items-center justify-center text-slate-400 dark:text-slate-500" aria-hidden="true">
            {leadingIcon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          type={revealed ? "text" : "password"}
          disabled={disabled}
          className={`${BASE_INPUT_CLASSES} ${leadingIcon ? "pl-11" : ""} pr-11 ${invalid ? ERROR_CLASSES : ""} ${className ?? ""}`}
          aria-invalid={invalid || undefined}
          aria-describedby={error ? errorId : undefined}
          {...inputProps}
        />
        <button
          type="button"
          onClick={() => setRevealed((current) => !current)}
          disabled={disabled}
          aria-label={revealed ? "Hide password" : "Show password"}
          aria-pressed={revealed}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-xl text-slate-400 transition-colors hover:text-slate-600 disabled:cursor-not-allowed dark:text-slate-500 dark:hover:text-slate-200"
        >
          {revealed ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
      <FieldError id={errorId} message={error} />
    </div>
  );
});
