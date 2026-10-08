import { Newspaper } from "lucide-react";

import { SectionHeading } from "../common/SectionHeading";

/**
 * The project has no news or sentiment service yet (that phase isn't built),
 * so this is an honest placeholder: it says so plainly and shows no
 * articles. When a news API exists, replace the body with a real list.
 */
export function NewsPlaceholder() {
  return (
    <section aria-labelledby="market-news-heading">
      <SectionHeading id="market-news-heading" title="Market News" />
      <div className="flex items-start gap-3 rounded-lg border border-dashed border-slate-300 px-4 py-5 dark:border-slate-700">
        <Newspaper className="mt-0.5 h-5 w-5 flex-shrink-0 text-slate-400" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">News &amp; sentiment — coming later</p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            News and sentiment integration will be connected in a future phase. No articles are shown until then.
          </p>
        </div>
      </div>
    </section>
  );
}
