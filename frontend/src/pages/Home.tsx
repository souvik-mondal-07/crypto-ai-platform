import { useEffect } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

import { PageContainer } from "../components/layout/PageContainer";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { useSystemStore } from "../store/systemStore";
import { useAuthStore } from "../store/authStore";

function StatusRow({
  label,
  online,
  checking = false,
}: {
  label: string;
  online: boolean;
  checking?: boolean;
}) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-3 last:border-0">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      {checking ? (
        <span className="flex items-center gap-1.5 text-sm text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Checking...
        </span>
      ) : online ? (
        <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-600">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          Online
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-sm font-semibold text-red-600">
          <XCircle className="h-4 w-4" aria-hidden="true" />
          Offline
        </span>
      )}
    </div>
  );
}

export function Home() {
  const { backendStatus, errorMessage, checkBackendHealth } = useSystemStore();
  const { isAuthenticated, user } = useAuthStore();

  useEffect(() => {
    checkBackendHealth();
  }, [checkBackendHealth]);

  return (
    <PageContainer>
      <div className="flex flex-col items-center text-center">
        <img src="/logo.svg" alt="" className="mb-4 h-14 w-14" />
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Crypto AI Platform
        </h1>
        <p className="mt-2 max-w-md text-sm text-slate-500">
          AI-powered cryptocurrency market analysis and decision-support
          platform. Foundation + market-data engine + authentication —
          Steps 1–4.
        </p>
      </div>

      <div className="mt-10 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-2 text-lg font-semibold text-slate-800">
          System Status
        </h2>
        <StatusRow label="Frontend" online={true} />
        <StatusRow
          label="Backend"
          online={backendStatus === "online"}
          checking={backendStatus === "checking"}
        />
      </div>

      {backendStatus === "offline" && errorMessage && (
        <div className="mt-4">
          <ErrorMessage message={`Backend Offline — ${errorMessage}`} />
        </div>
      )}

      <div className="mt-6 flex justify-center gap-4 text-sm">
        <Link
          to="/market-test"
          className="font-medium text-sky-600 hover:text-sky-700 hover:underline"
        >
          View market data test page →
        </Link>
        {isAuthenticated ? (
          <Link to="/dashboard" className="font-medium text-sky-600 hover:text-sky-700 hover:underline">
            Go to dashboard ({user?.name}) →
          </Link>
        ) : (
          <Link to="/login" className="font-medium text-sky-600 hover:text-sky-700 hover:underline">
            Log in →
          </Link>
        )}
      </div>
    </PageContainer>
  );
}
