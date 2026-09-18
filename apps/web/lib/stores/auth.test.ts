import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useAuthStore } from "./auth";
import { services } from "@/lib/services";

describe("useAuthStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.setState({ user: null, loaded: false, error: null });
  });
  afterEach(() => vi.restoreAllMocks());

  it("refresh loads the session (null when signed out)", async () => {
    await useAuthStore.getState().refresh();
    expect(useAuthStore.getState()).toMatchObject({ user: null, loaded: true, error: null });
  });

  it("signUp, signOut, signIn round trip", async () => {
    expect(await useAuthStore.getState().signUp("a@b.co", "longenough", "Ada")).toBe(true);
    expect(useAuthStore.getState().user?.name).toBe("Ada");
    expect(useAuthStore.getState().loaded).toBe(true);
    await useAuthStore.getState().signOut();
    expect(useAuthStore.getState().user).toBeNull();
    expect(await useAuthStore.getState().signIn("a@b.co", "longenough")).toBe(true);
    expect(useAuthStore.getState().user?.email).toBe("a@b.co");
  });

  it("failed sign-in sets error and leaves user null", async () => {
    expect(await useAuthStore.getState().signIn("nobody@b.co", "longenough")).toBe(false);
    expect(useAuthStore.getState().error?.code).toBe("not_found");
    expect(useAuthStore.getState().user).toBeNull();
    // A later success clears the error.
    expect(await useAuthStore.getState().guest()).toBe(true);
    expect(useAuthStore.getState().error).toBeNull();
    expect(useAuthStore.getState().user?.name).toBe("Guest");
  });

  it("signInWith and updateProfile update the user", async () => {
    expect(await useAuthStore.getState().signInWith("apple")).toBe(true);
    expect(useAuthStore.getState().user?.email).toBe("you@icloud.com");
    expect(await useAuthStore.getState().updateProfile({ name: "Grace" })).toBe(true);
    expect(useAuthStore.getState().user?.name).toBe("Grace");
  });

  it("refresh failure sets error and still marks loaded", async () => {
    vi.spyOn(services.auth, "current").mockResolvedValueOnce({ ok: false, error: { code: "storage_unavailable", message: "nope" } });
    await useAuthStore.getState().refresh();
    expect(useAuthStore.getState().loaded).toBe(true);
    expect(useAuthStore.getState().error?.code).toBe("storage_unavailable");
  });
});
