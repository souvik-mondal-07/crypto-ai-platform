import { AlertTriangle } from "lucide-react";

import type { NewsFeedStatus } from "../../types/news";
import { formatRelativeTime } from "../../utils/formatters";
import { describeSyncError } from "../../utils/newsErrors";

/**
 * Explains the state of the pipeline behind the feed, using the backend's own
 * status — so a stale feed or missing sentiment is never silently unexplained.
 */
export function NewsFeedNotice({ status, showSentiment = true }: { status: NewsFeedStatus; showSentiment?: boolean }) {
  const messages: string[] = [];
  const syncReason = describeSyncError(status.last_sync_error_code);
  if (syncReason) {
    messages.push(
      `The latest refresh didn't complete (${syncReason}). Showing stored articles` +
        (status.last_sync_success_at ? `; last successful refresh ${formatRelativeTime(status.last_sync_success_at)}.` : ".")
    );
  }
  if (showSentiment && status.sentiment_model_status === "unavailable") {
    messages.push("Sentiment analysis is currently unavailable, so articles are shown without a sentiment label.");
  }
  if (messages.length === 0) return null;

  return (
    <div role="status" className="mb-3 space-y-2">
      {messages.map((message) => (
        <div
          key={message}
          className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
          <p>{message}</p>
        </div>
      ))}
    </div>
  );
}
