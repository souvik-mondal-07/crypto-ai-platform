import { useEffect, useState } from "react";

/**
 * Whole seconds left until `until` (epoch ms), ticking once a second ONLY while a countdown is active
 * (no timer at all when there is nothing to count down to).
 */
export function useCountdownSeconds(until: number | null): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (until === null || until <= Date.now()) return;
    setNow(Date.now());
    const timer = window.setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (current >= until) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [until]);

  if (until === null) return 0;
  return Math.max(0, Math.ceil((until - Math.max(now, Date.now())) / 1000));
}
