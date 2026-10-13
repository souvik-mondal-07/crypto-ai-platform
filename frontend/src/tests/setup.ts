import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

import { useToastStore } from "../store/toastStore";

// Toasts live in a global store; make sure one test's notifications never leak into the next.
afterEach(() => {
  useToastStore.getState().clear();
});
