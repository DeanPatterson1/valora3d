import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useCreditsStore } from "./credits";
import { services } from "@/lib/services";

describe("useCreditsStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useCreditsStore.setState({ balance: 0, ledger: [], loaded: false, error: null });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it("refreshes balance and ledger, and adds credits", async () => {
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(100);
    expect(useCreditsStore.getState().loaded).toBe(true);
    await useCreditsStore.getState().add(50, "pack_purchase");
    expect(useCreditsStore.getState().balance).toBe(150);
    expect(useCreditsStore.getState().error).toBeNull();
  });

  it("add sets error when the post fails and keeps the balance", async () => {
    await useCreditsStore.getState().refresh();
    vi.spyOn(services.credits, "post").mockResolvedValueOnce({ ok: false, error: { code: "storage_unavailable", message: "nope" } });
    await useCreditsStore.getState().add(50, "pack_purchase");
    expect(useCreditsStore.getState().error?.code).toBe("storage_unavailable");
    expect(useCreditsStore.getState().balance).toBe(100);
  });

  it("refresh failure sets error and keeps the previous balance instead of 0", async () => {
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(100);
    vi.spyOn(services.credits, "balance").mockResolvedValueOnce({ ok: false, error: { code: "storage_unavailable", message: "nope" } });
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().error?.code).toBe("storage_unavailable");
    expect(useCreditsStore.getState().balance).toBe(100);
    expect(useCreditsStore.getState().loaded).toBe(true);
  });
});
