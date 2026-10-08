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
 * away and nothing is lazily unmounted.
 */
export function CoinSectionNav({ sections }: CoinSectionNavProps) {
  function jump(id: string) {
    const element = document.getElementById(id);
    if (element && typeof element.scrollIntoView === "function") {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  return (
    <nav
      aria-label="Coin sections"
      className="sticky top-[57px] z-[5] -mx-4 mt-4 flex gap-1 overflow-x-auto border-b border-slate-200 bg-slate-50/95 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
    >
      {sections.map((section) => (
        <button
          key={section.id}
          type="button"
          onClick={() => jump(section.id)}
          className="whitespace-nowrap border-b-2 border-transparent px-3 py-2 text-sm font-medium text-slate-500 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:text-slate-400 dark:hover:text-slate-100"
        >
          {section.label}
        </button>
      ))}
    </nav>
  );
}
