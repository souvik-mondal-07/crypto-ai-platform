import type { ReactNode } from "react";

interface SectionHeadingProps {
  title: string;
  description?: string;
  /** Right-aligned controls (tabs, selectors, links). */
  actions?: ReactNode;
  id?: string;
}

/** Consistent section title row used across Dashboard, Markets and Coin Details. */
export function SectionHeading({ title, description, actions, id }: SectionHeadingProps) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 id={id} className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          {title}
        </h2>
        {description && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{description}</p>}
      </div>
      {actions}
    </div>
  );
}
