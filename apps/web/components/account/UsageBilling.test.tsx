// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LowBalanceNote } from "@/components/studio/RenderPanel";
import { SettingsScreen } from "@/components/settings/SettingsScreen";
import { renderCost } from "@/lib/render/cost";
import type { CreditTransaction } from "@/lib/schema";
import { services } from "@/lib/services";
import { KEYS, writeJson } from "@/lib/services/local/storage";
import { useAuthStore } from "@/lib/stores/auth";
import { useCreditsStore } from "@/lib/stores/credits";
import { ProfileScreen } from "./ProfileScreen";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

beforeEach(async () => {
  localStorage.clear();
  await services.auth.signUp("ada@example.com", "longenough", "Ada Lovelace");
  await useAuthStore.getState().refresh();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function seedLedger(n: number) {
  const ledger: CreditTransaction[] = [{ id: "s", amount: 50, reason: "starting_balance", projectId: null, createdAt: 1 }];
  for (let i = 0; i < n; i++) ledger.push({ id: `t${i}`, amount: -3, reason: "render_preview", projectId: null, createdAt: 10 + i });
  ledger.push({ id: "pack", amount: 500, reason: "pack_purchase", projectId: null, createdAt: 1000 });
  writeJson(KEYS.ledger, ledger);
  useCreditsStore.setState({ balance: 50 - 3 * n + 500, ledger, loaded: true, error: null });
}

describe("Profile -> Usage & billing", () => {
  it("opens on Overview; the tab shows plan, balance and the credit history in plain words", async () => {
    seedLedger(2);
    render(<ProfileScreen />);
    expect(screen.getByRole("group", { name: "Usage" })).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Usage & billing" }));
    expect(await screen.findByText("One-time credits, no renewal.")).toBeTruthy();
    expect(screen.getByText("544 credits")).toBeTruthy();
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[0]?.querySelector("span")?.textContent)).toEqual([
      "Credit pack 500",
      "Preview render",
      "Preview render",
      "Starting credits",
    ]);
    // Amount and running balance, newest first.
    expect(within(rows[0]!).getByText("+500")).toBeTruthy();
    expect(within(rows[0]!).getByText("544")).toBeTruthy();
    expect(within(rows[1]!).getByText("−3")).toBeTruthy();
    expect(within(rows[1]!).getByText("44")).toBeTruthy();
    // Local mode: no renders, no billing portal.
    expect(await screen.findByText(/No renders yet/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Manage billing/ })).toBeNull();
  });

  it("pages the credit history 20 at a time", async () => {
    seedLedger(25); // 27 rows
    render(<ProfileScreen initialTab="billing" />);
    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(21);
    const pager = screen.getByRole("navigation", { name: "Credit history pages" });
    expect((within(pager).getByRole("button", { name: "Newer" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(pager).getByRole("button", { name: "Older" }));
    await waitFor(() => expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(8));
    expect(within(pager).getByText("Page 2")).toBeTruthy();
    expect((within(pager).getByRole("button", { name: "Older" }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(screen.getByRole("table")).getByText("Starting credits")).toBeTruthy();
  });
});

describe("low-balance nudge", () => {
  it("shows one quiet line linking to pricing only below a Final render's cost", () => {
    const cost = renderCost("final");
    const { rerender } = render(<LowBalanceNote balance={cost - 1} />);
    const note = screen.getByTestId("low-balance");
    expect(note.textContent).toContain(`A Final render uses ${cost}`);
    expect(within(note).getByRole("link", { name: "Get credits" }).getAttribute("href")).toBe("/pricing");
    rerender(<LowBalanceNote balance={cost} />);
    expect(screen.queryByTestId("low-balance")).toBeNull();
  });
});

describe("Settings -> Notifications", () => {
  it("render-ready emails default on and the switch saves the preference", async () => {
    render(<SettingsScreen initialSection="notifications" />);
    const sw = screen.getByRole("switch", { name: "Email me when a render is ready" });
    expect(sw.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(sw);
    await waitFor(() => expect(useAuthStore.getState().user?.emailRenderReady).toBe(false));
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("false");
    const stored = await services.auth.current();
    expect(stored.ok && stored.value?.emailRenderReady).toBe(false);
  });
});
