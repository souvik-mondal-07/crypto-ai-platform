
import type { ReactNode } from "react";

interface AuthLayoutProps {
  variant?: "login" | "signup";
  title: string;
  subtitle?: string;
  children: ReactNode;
}

export function AuthLayout({
  variant = "login",
  title,
  subtitle,
  children,
}: AuthLayoutProps) {
  return (
    <div
      data-auth-variant={variant}
      className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-950"
    >
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <img
            src="/logo.svg"
            alt=""
            className="mx-auto mb-3 h-10 w-10"
          />
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
            {title}
          </h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        <div className="card p-5 sm:p-6">{children}</div>
      </div>
    </div>
  );
}
