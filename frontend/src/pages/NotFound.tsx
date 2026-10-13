import { Link } from "react-router-dom";

import { PageContainer } from "../components/layout/PageContainer";

export function NotFound() {
  return (
    <PageContainer>
      <div className="flex flex-col items-center text-center">
        <h1 className="text-5xl font-bold text-slate-900">404</h1>
        <p className="mt-2 text-sm text-slate-500">
          The page you're looking for doesn't exist.
        </p>
        <Link
          to="/"
          className="btn-primary mt-6"
        >
          Back to Home
        </Link>
      </div>
    </PageContainer>
  );
}
