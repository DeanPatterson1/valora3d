// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/stores/auth";
import { services } from "@/lib/services";
import { AuthGate } from "./AuthGate";

const replace = vi.fn();
let pathname = "/projects";
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => pathname,
  useSearchParams: () => new URLSearchParams(search),
}));

beforeEach(() => {
  localStorage.clear();
  replace.mockClear();
  pathname = "/projects";
  search = "";
  useAuthStore.setState({ user: null, loaded: false, error: null });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AuthGate", () => {
  it("shows a skeleton, then redirects to /login with the wanted path when signed out", async () => {
    search = "new=1";
    render(
      <AuthGate>
        <p>secret</p>
      </AuthGate>,
    );
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(screen.queryByText("secret")).toBeNull();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fprojects%3Fnew%3D1"));
    expect(screen.queryByText("secret")).toBeNull();
  });

  it("renders children once a session is found", async () => {
    await services.auth.continueAsGuest();
    render(
      <AuthGate>
        <p>secret</p>
      </AuthGate>,
    );
    await waitFor(() => expect(screen.getByText("secret")).toBeTruthy());
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects when the user signs out later", async () => {
    await services.auth.continueAsGuest();
    pathname = "/settings";
    render(
      <AuthGate>
        <p>secret</p>
      </AuthGate>,
    );
    await waitFor(() => expect(screen.getByText("secret")).toBeTruthy());
    await useAuthStore.getState().signOut();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fsettings"));
  });
});
