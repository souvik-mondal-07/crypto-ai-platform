import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PasswordField, TextField } from "./FormFields";

describe("TextField", () => {
  it("sets an explicit text and background colour in both themes", () => {
    render(<TextField label="Email" />);
    const input = screen.getByLabelText("Email");
    const className = input.getAttribute("class") ?? "";

    // The original bug: no text/bg class meant the input inherited
    // body's near-white colour in dark mode over a white field.
    expect(className).toContain("text-slate-900");
    expect(className).toContain("bg-white");
    expect(className).toContain("dark:text-slate-100");
    expect(className).toContain("dark:bg-slate-900");
  });

  it("associates its label with the input", async () => {
    render(<TextField label="Email" />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email"), "someone@example.com");
    expect(screen.getByLabelText("Email")).toHaveValue("someone@example.com");
  });

  it("marks the field invalid when hasError is set", () => {
    render(<TextField label="Email" hasError />);
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("PasswordField", () => {
  it("masks the value by default", () => {
    render(<PasswordField label="Password" />);
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  });

  it("applies the same explicit colours to masked dots as to normal text", () => {
    render(<PasswordField label="Password" />);
    const className = screen.getByLabelText("Password").getAttribute("class") ?? "";
    expect(className).toContain("text-slate-900");
    expect(className).toContain("bg-white");
    expect(className).toContain("dark:text-slate-100");
    expect(className).toContain("dark:bg-slate-900");
  });

  it("toggles between masked and revealed without losing the value", async () => {
    const user = userEvent.setup();
    render(<PasswordField label="Password" defaultValue="" />);

    const input = screen.getByLabelText("Password");
    await user.type(input, "a-real-password");
    expect(input).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: /show password/i }));
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("Password")).toHaveValue("a-real-password");

    await user.click(screen.getByRole("button", { name: /hide password/i }));
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("Password")).toHaveValue("a-real-password");
  });

  it("exposes the toggle state to assistive technology", async () => {
    const user = userEvent.setup();
    render(<PasswordField label="Password" />);

    const toggle = screen.getByRole("button", { name: /show password/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    await user.click(toggle);
    expect(screen.getByRole("button", { name: /hide password/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("disables the toggle when the field is disabled", () => {
    render(<PasswordField label="Password" disabled />);
    expect(screen.getByRole("button", { name: /show password/i })).toBeDisabled();
  });
});
