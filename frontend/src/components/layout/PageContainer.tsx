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
      id="main-content"
      tabIndex={-1}
      className={`mx-auto w-full min-w-0 px-4 py-6 focus:outline-none sm:px-6 sm:py-8 lg:px-8 ${wide ? "max-w-[1680px]" : "max-w-3xl"}`}
    >
      {children}
    </main>
  );
}
