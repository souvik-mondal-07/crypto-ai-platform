import type { ReactNode } from "react";

interface PageContainerProps {
  children: ReactNode;
  /** Widens the container for data-dense pages (Dashboard, Markets). Defaults to the original narrow width used by Home/MarketTest/auth pages. */
  wide?: boolean;
}

/**
 * Basic page container providing consistent spacing/width.
 */
export function PageContainer({ children, wide = false }: PageContainerProps) {
  return (
    <main
      className={`mx-auto w-full px-4 py-10 sm:px-6 lg:px-8 ${wide ? "max-w-7xl" : "max-w-3xl"}`}
    >
      {children}
    </main>
  );
}
