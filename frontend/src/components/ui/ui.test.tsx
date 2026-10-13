import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { toast, useToastStore } from "../../store/toastStore";
import { ConfirmDialog } from "./ConfirmDialog";
import { DataKindBadge } from "./DataKindBadge";
import { PageHeader } from "./PageHeader";
import { MetricSkeleton, Skeleton, TableSkeleton } from "./Skeleton";
import { ToastViewport } from "./ToastViewport";

describe("ConfirmDialog", () => {
  function setup() {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog title="Remove Bitcoin?" confirmLabel="Remove" destructive onConfirm={onConfirm} onCancel={onCancel}>
        This cannot be undone.
      </ConfirmDialog>
    );
    return { onConfirm, onCancel };
  }

  it("is a labelled, described alert dialog", () => {
    setup();
    const dialog = screen.getByRole("alertdialog", { name: "Remove Bitcoin?" });
    expect(dialog).toHaveAccessibleDescription("This cannot be undone.");
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("focuses the safe (Cancel) action first", () => {
    setup();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("confirms and cancels via buttons, and cancels with Escape", async () => {
    const { onConfirm, onCancel } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("keeps Tab focus inside the dialog", async () => {
    setup();
    const user = userEvent.setup();
    await user.tab(); // Cancel -> Remove
    expect(screen.getByRole("button", { name: "Remove" })).toHaveFocus();
    await user.tab(); // wraps back to Cancel
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });
});

describe("toasts", () => {
  it("shows a message in a polite live region and lets the user dismiss it", async () => {
    render(<ToastViewport />);
    act(() => toast.success("Alert created."));
    expect(await screen.findByText("Alert created.")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByText("Alert created.")).not.toBeInTheDocument();
  });

  it("does not stack an identical message twice, and caps how many are visible", () => {
    act(() => {
      toast.info("Same");
      toast.info("Same");
    });
    expect(useToastStore.getState().toasts).toHaveLength(1);
    act(() => {
      for (let i = 0; i < 10; i++) toast.info(`Message ${i}`);
    });
    expect(useToastStore.getState().toasts.length).toBeLessThanOrEqual(4);
  });
});

describe("DataKindBadge", () => {
  it.each([
    ["observed", /observed data/i, /not a forecast/i],
    ["model", /model estimate/i, /not a guarantee/i],
    ["risk", /risk assessment/i, /not financial advice/i],
    ["ai", /ai-generated/i, /can be wrong/i],
  ] as const)("labels %s content and says what it is", (kind, label, hint) => {
    render(<DataKindBadge kind={kind} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText(hint)).toBeInTheDocument();
  });
});

describe("layout primitives", () => {
  it("PageHeader renders the heading, subtitle and actions", () => {
    render(<PageHeader title="Portfolio" subtitle="Track holdings" actions={<button>Add</button>} />);
    expect(screen.getByRole("heading", { level: 1, name: "Portfolio" })).toBeInTheDocument();
    expect(screen.getByText("Track holdings")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });

  it("skeletons are hidden from assistive tech, except the table's labelled status", () => {
    const { container } = render(
      <MemoryRouter>
        <Skeleton className="h-3" />
        <MetricSkeleton />
        <TableSkeleton label="Loading coins" />
      </MemoryRouter>
    );
    expect(screen.getByRole("status", { name: "Loading coins" })).toBeInTheDocument();
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0);
  });
});
