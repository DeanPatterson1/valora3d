// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/stores/auth";
import { services } from "@/lib/services";
import { LoginScreen } from "./LoginScreen";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(search),
}));

beforeEach(() => {
  localStorage.clear();
  search = "";
  replace.mockClear();
  useAuthStore.setState({ user: null, loaded: false, error: null });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("LoginScreen", () => {
  it("shows provider failures instead of silently staying on the form", async () => {
    vi.spyOn(services.auth, "signInWith").mockResolvedValue({ ok: false, error: { code: "storage_unavailable", message: "Browser storage is unavailable." } });
    render(<LoginScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Browser storage is unavailable."));
    expect(replace).not.toHaveBeenCalled();
  });

  it("reveals the password field once the email is valid", () => {
    render(<LoginScreen />);
    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeTruthy();
    expect(screen.queryByLabelText("Password")).toBeNull();
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "ada@exam" } });
    expect(screen.queryByLabelText("Password")).toBeNull();
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "ada@example.com" } });
    expect(screen.getByLabelText("Password")).toBeTruthy();
  });

  it("Continue with an invalid email shows an inline error instead of revealing the password", () => {
    render(<LoginScreen />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "nope" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByLabelText("Email address").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getAllByText("Enter a valid email address.").length).toBeGreaterThan(0);
    expect(screen.queryByLabelText("Password")).toBeNull();
  });

  it("shows the service error for an unknown email and does not navigate", async () => {
    render(<LoginScreen />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "nobody@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "longenough" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(screen.getAllByText("No account with that email").length).toBeGreaterThan(0));
    expect(replace).not.toHaveBeenCalled();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("signs in an existing account and honours ?next", async () => {
    await services.auth.signUp("ada@example.com", "longenough", "Ada");
    await services.auth.signOut();
    search = "next=%2Fsettings";
    render(<LoginScreen />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "ada@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "longenough" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/settings"));
    expect(useAuthStore.getState().user?.name).toBe("Ada");
  });

  it("ignores an off-site ?next", async () => {
    await services.auth.signUp("ada@example.com", "longenough", "Ada");
    search = "next=https%3A%2F%2Fevil.example";
    render(<LoginScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Continue as guest" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/projects"));
  });

  it("guest path signs in the guest user and goes to /projects", async () => {
    render(<LoginScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Continue as guest" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/projects"));
    expect(useAuthStore.getState().user?.name).toBe("Guest");
  });

  it("provider button signs in the demo user", async () => {
    render(<LoginScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/projects"));
    expect(useAuthStore.getState().user?.email).toBe("you@gmail.com");
  });
});
