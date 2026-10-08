import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePolling } from "./usePolling";

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
}

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setVisibility("visible");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("calls the callback on the given interval", () => {
    const callback = vi.fn();
    renderHook(() => usePolling(callback, 1000));

    expect(callback).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(callback).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(2000);
    expect(callback).toHaveBeenCalledTimes(3);
  });

  it("does not poll when enabled is false", () => {
    const callback = vi.fn();
    renderHook(() => usePolling(callback, 1000, false));

    vi.advanceTimersByTime(5000);
    expect(callback).not.toHaveBeenCalled();
  });

  it("always calls the latest callback, even if it changes identity between renders", () => {
    const firstCallback = vi.fn();
    const secondCallback = vi.fn();
    const { rerender } = renderHook(({ cb }) => usePolling(cb, 1000), {
      initialProps: { cb: firstCallback },
    });

    rerender({ cb: secondCallback });
    vi.advanceTimersByTime(1000);

    expect(firstCallback).not.toHaveBeenCalled();
    expect(secondCallback).toHaveBeenCalledTimes(1);
  });

  it("skips a tick while the tab is hidden", () => {
    const callback = vi.fn();
    setVisibility("hidden");
    renderHook(() => usePolling(callback, 1000));

    vi.advanceTimersByTime(3000);
    expect(callback).not.toHaveBeenCalled();
  });

  it("fires immediately when the tab becomes visible again", () => {
    const callback = vi.fn();
    setVisibility("hidden");
    renderHook(() => usePolling(callback, 1000));

    setVisibility("visible");
    document.dispatchEvent(new Event("visibilitychange"));

    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("cleans up the interval and listener on unmount", () => {
    const callback = vi.fn();
    const { unmount } = renderHook(() => usePolling(callback, 1000));

    unmount();
    vi.advanceTimersByTime(5000);

    expect(callback).not.toHaveBeenCalled();
  });
});
