import { useEffect, useState } from "react";

export interface CoinSection {
  id: string;
  label: string;
}

interface CoinSectionNavProps {
  sections: CoinSection[];
}

/**
 * In-page navigation for the Coin Details workspace. It lists ONLY sections
 * that exist on the page, and scrolls rather than hiding content, so every analysis stays one click
 * away and nothing is lazily unmounted. The section currently in view is highlighted (where the browser
 * supports IntersectionObserver).
 */
export function CoinSectionNav({ sections }: CoinSectionNavProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  // Depend on the ids (a stable string), not the array, whose identity changes on every parent render.
  const sectionIds = sections.map((section) => section.id).join(",");

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const visible = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.set(entry.target.id, entry.boundingClientRect.top);
          else visible.delete(entry.target.id);
        }
        // The topmost section that is in the viewport band is "current".
        const first = [...visible.entries()].sort((a, b) => a[1] - b[1])[0];
        if (first) setActiveId(first[0]);
      },
      { rootMargin: "-20% 0px -65% 0px" }
    );
    for (const id of sectionIds.split(",")) {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [sectionIds]);

  function jump(id: string) {
    const element = document.getElementById(id);
    if (element && typeof element.scrollIntoView === "function") {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  return (
    <nav
      aria-label="Coin sections"
      className="sticky top-[101px] z-[5] -mx-4 mt-4 flex gap-1 overflow-x-auto border-b border-slate-200 bg-slate-50/95 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 sm:-mx-6 sm:px-6 lg:top-[57px] lg:-mx-8 lg:px-8"
    >
      {sections.map((section) => {
        const active = section.id === activeId;
        return (
          <button
            key={section.id}
            type="button"
            onClick={() => jump(section.id)}
            aria-current={active ? "true" : undefined}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
              active
                ? "border-sky-500 text-sky-700 dark:text-sky-300"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
            }`}
          >
            {section.label}
          </button>
        );
      })}
    </nav>
  );
}
