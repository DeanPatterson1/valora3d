// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/stores/auth";
import { services } from "@/lib/services";
import { SignupScreen } from "./SignupScreen";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(""),
}));

beforeEach(() => {
  localStorage.clear();
  replace.mockClear();
  useAuthStore.setState({ user: null, loaded: false, error: null });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function fill(name: string, email: string, password: string) {
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: name } });
  fireEvent.change(screen.getByLabelText("Email address"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
}

describe("SignupScreen", () => {
  it("shows all three fields at once and validates each inline", () => {
    render(<SignupScreen />);
    expect(screen.getByLabelText("Password")).toBeTruthy();
    fill("", "nope", "short");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getAllByText("Enter your name.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Enter a valid email address.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Use at least 8 characters.").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Password").getAttribute("aria-invalid")).toBe("true");
    expect(replace).not.toHaveBeenCalled();
  });

  it("clears a field error as the field is edited", () => {
    render(<SignupScreen />);
    fill("Ada", "ada@example.com", "short");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByLabelText("Password").getAttribute("aria-invalid")).toBe("true");
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "longenough" } });
    expect(screen.getByLabelText("Password").getAttribute("aria-invalid")).toBeNull();
  });

  it("creates the account and lands on /projects", async () => {
    render(<SignupScreen />);
    fill("Ada", "ada@example.com", "longenough");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/projects"));
    expect(useAuthStore.getState().user).toMatchObject({ name: "Ada", email: "ada@example.com", plan: "free" });
  });

  it("reports an existing email from the service", async () => {
    await services.auth.signUp("ada@example.com", "longenough", "Ada");
    await services.auth.signOut();
    render(<SignupScreen />);
    fill("Ada", "ada@example.com", "longenough");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(screen.getAllByText("An account with that email already exists").length).toBeGreaterThan(0));
    expect(replace).not.toHaveBeenCalled();
  });
});
