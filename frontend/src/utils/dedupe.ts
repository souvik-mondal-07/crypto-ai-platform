/**
 * Shares one in-flight promise between callers that ask for the same thing.
 *
 * Several components (Dashboard sections, the Markets page, React 18
 * StrictMode's double-invoked effects, a polling tick landing on top of a
 * manual retry) can all request the same endpoint at nearly the same
 * moment. Without this each would fire its own HTTP request. With it they
 * all await the single request that is already running; the entry is
 * removed as soon as it settles, so the NEXT call (e.g. the next polling
 * tick) performs a fresh request — this is request coalescing, not caching.
 *
 * An entry older than MAX_SHARE_MS is no longer shared: if a request hangs,
 * a user's Retry starts a new one instead of re-joining the stuck call.
 */
const MAX_SHARE_MS = 20_000;

interface Entry {
  promise: Promise<unknown>;
  startedAt: number;
}

const inflight = new Map<string, Entry>();

export function dedupe<T>(key: string, factory: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key);
  if (existing && Date.now() - existing.startedAt < MAX_SHARE_MS) {
    return existing.promise as Promise<T>;
  }

  // `new Promise` also converts a synchronous throw (or a non-promise return)
  // from `factory` into an ordinary rejection/resolution.
  const promise: Promise<T> = new Promise<T>((resolve) => resolve(factory())).finally(() => {
    // Only clear our own entry (a newer call could have replaced it).
    if (inflight.get(key)?.promise === promise) inflight.delete(key);
  });
  inflight.set(key, { promise, startedAt: Date.now() });
  return promise;
}

/** Test helper: forget every in-flight entry. */
export function resetDedupe(): void {
  inflight.clear();
}
