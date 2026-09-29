// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/stores/auth";
import { services } from "@/lib/services";
import { SIGNUP_OFFER, SignupScreen } from "./SignupScreen";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(search),
}));

beforeEach(() => {
  search = "";
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

  it("restates the offer, links the terms, and cross-links to log in keeping the destination", () => {
    search = "plan=creator";
    render(<SignupScreen />);
    expect(screen.getByText(SIGNUP_OFFER)).toBeTruthy();
    expect(SIGNUP_OFFER).toBe("Start free with 10 credits, enough for 2 Previews. No card needed.");
    expect(screen.getByRole("link", { name: "Terms" }).getAttribute("href")).toBe("/terms");
    expect(screen.getByRole("link", { name: "Log in" }).getAttribute("href")).toBe("/login?next=%2Fpricing%3Fcheckout%3Dplan%253Acreator");
  });

  it("carries a chosen plan through signup to that plan's checkout", async () => {
    search = "plan=creator";
    const signUp = vi.spyOn(services.auth, "signUp");
    render(<SignupScreen />);
    fill("Ada", "ada@example.com", "longenough");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/pricing?checkout=plan%3Acreator"));
    // The same destination goes to the service, which puts it in the confirmation email and the OAuth return.
    expect(signUp.mock.calls[0][4]).toBe("/pricing?checkout=plan%3Acreator");
  });

  it("sends someone already signed in straight on, but keeps the form for a Local guest", async () => {
    search = "next=%2Fprojects%3Fnew%3D1";
    await services.auth.signUp("ada@example.com", "longenough", "Ada");
    render(<SignupScreen />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/projects?new=1"));
    cleanup();
    replace.mockClear();
    await services.auth.continueAsGuest();
    render(<SignupScreen />);
    await new Promise((r) => setTimeout(r, 20));
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Create account" })).toBeTruthy();
  });
});
