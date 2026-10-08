import { useEffect, useRef } from "react";

/**
 * Calls `callback` on a fixed interval for as long as the component is
 * mounted, without ever re-registering the interval when `callback`
 * itself changes identity between renders (the common footgun with a
 * naive `setInterval` + `useEffect([callback])`).
 *
 * Pauses while the tab is hidden (`document.visibilityState !==
 * "visible"`) and immediately fires one call the moment it becomes
 * visible again — so a backgrounded tab doesn't keep silently hitting
 * the API, and coming back to the tab doesn't leave stale data
 * sitting for up to a full interval before refreshing.
 *
 * Pass `enabled = false` to disable polling entirely (e.g. while a
 * dependent value like a coin id is still undefined) without having
 * to conditionally call the hook itself.
 */
export function usePolling(callback: () => void, intervalMs: number, enabled: boolean = true): void {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!enabled || intervalMs <= 0) return;

    const tick = () => {
      if (document.visibilityState === "visible") {
        callbackRef.current();
      }
    };

    const intervalId = window.setInterval(tick, intervalMs);

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        callbackRef.current();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [intervalMs, enabled]);
}
