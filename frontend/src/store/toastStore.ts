import { create } from "zustand";

/**
 * Lightweight app-wide toast queue for the outcome of user actions ("Added to watchlist", "Alert deleted").
 * Purely presentational: it holds messages, never data. Rendered by <ToastViewport /> (mounted once in AppShell).
 */
export type ToastKind = "success" | "info" | "error";
export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

const MAX_VISIBLE = 4;
let nextId = 1;

interface ToastState {
  toasts: Toast[];
  push: (kind: ToastKind, message: string) => void;
  dismiss: (id: number) => void;
  clear: () => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (kind, message) =>
    set((state) => {
      // An identical message already on screen is not stacked again.
      if (state.toasts.some((toast) => toast.kind === kind && toast.message === message)) return state;
      return { toasts: [...state.toasts, { id: nextId++, kind, message }].slice(-MAX_VISIBLE) };
    }),
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
  clear: () => set({ toasts: [] }),
}));

/** Convenience for non-React code (stores, hooks). */
export const toast = {
  success: (message: string) => useToastStore.getState().push("success", message),
  info: (message: string) => useToastStore.getState().push("info", message),
  error: (message: string) => useToastStore.getState().push("error", message),
};
