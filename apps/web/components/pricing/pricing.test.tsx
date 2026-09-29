// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/stores/auth";
import type { User } from "@/lib/schema";
import { PLANS } from "@/lib/pricing";
import { useCreditsStore } from "@/lib/stores/credits";
import { useToastStore } from "@/components/ui/Toast";
import { ActionCostTable } from "./ActionCostTable";
import { CreditPacks, perCredit } from "./CreditPacks";
import { PlanCards } from "./PlanCards";

describe("PlanCards", () => {
  beforeEach(() => {
    useCreditsStore.setState({ add: vi.fn(async () => {}), error: null });
    useToastStore.setState({ toasts: [] });
    useAuthStore.setState({ user: { id: "test-user" } as User, loaded: true });
  });
  afterEach(cleanup);

  it("renders three plans with Creator highlighted", () => {
    render(<PlanCards />);
    const list = screen.getByRole("list", { name: "Plans" });
    const cards = within(list).getAllByRole("listitem").filter((li) => li.hasAttribute("data-plan"));
    expect(cards.map((c) => c.getAttribute("data-plan"))).toEqual(["Free", "Creator", "Pro"]);
    expect(cards.filter((c) => c.hasAttribute("data-highlighted")).map((c) => c.getAttribute("data-plan"))).toEqual(["Creator"]);
    // No popularity claim: there are no customers to be popular with yet.
    expect(within(list).queryByText(/most popular/i)).toBeNull();
    // The free plan's price line reads "$0 Free · no card needed" rather than "$0 USD, no card".
    expect(within(cards[0]).getByText("Free · no card needed")).toBeTruthy();
    expect(within(cards[0]).queryByText("USD, no card")).toBeNull();
    expect(within(cards[1]).getByText("USD / month")).toBeTruthy();
    // Credits in renders, honest per plan: Free is never promised a Final.
    expect(cards.map((c) => within(c).getByTestId("plan-value").textContent)).toEqual([
      "10 credits = 2 Previews", "800 credits a month = 160 Previews or 8 Finals", "2,500 credits a month = 500 Previews or 25 Finals",
    ]);
    expect(screen.getAllByRole("button", { name: /^Choose plan/ })).toHaveLength(3);
  });

  it("choosing Creator adds 800 credits as a plan grant and toasts", async () => {
    const add = vi.fn(async () => {});
    useCreditsStore.setState({ add });
    render(<PlanCards />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Choose plan: Creator" }));
    });
    expect(add).toHaveBeenCalledWith(800, "plan_grant", undefined);
    expect(useToastStore.getState().toasts.map((t) => t.message)).toEqual(["Added 800 credits"]);
  });

  it("is repeatable", async () => {
    const add = vi.fn(async () => {});
    useCreditsStore.setState({ add });
    render(<PlanCards />);
    const btn = screen.getByRole("button", { name: "Choose plan: Creator" });
    await act(async () => { fireEvent.click(btn); });
    await act(async () => { fireEvent.click(btn); });
    expect(add).toHaveBeenCalledTimes(2);
  });

  it("toasts the store error when the grant fails", async () => {
    const add = vi.fn(async () => {
      useCreditsStore.setState({ error: { code: "storage", message: "Could not save credits" } });
    });
    useCreditsStore.setState({ add });
    render(<PlanCards />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Choose plan: Pro" }));
    });
    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0]).toMatchObject({ kind: "danger", message: "Could not save credits" });
  });

  it("sends signed-out visitors to signup without granting credits", () => {
    useAuthStore.setState({ user: null, loaded: true });
    render(<><PlanCards /><CreditPacks /></>);
    const links = screen.getAllByRole("link", { name: /Get started/ });
    expect(links).toHaveLength(7);
    // Signup carries the choice through to that item's checkout (lib/nav/next.ts); Free just starts a project.
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "/signup?next=%2Fprojects%3Fnew%3D1",
      "/signup?next=%2Fpricing%3Fcheckout%3Dplan%253Acreator",
      "/signup?next=%2Fpricing%3Fcheckout%3Dplan%253Apro",
      "/signup?next=%2Fpricing%3Fcheckout%3Dpack%253Afirst",
      "/signup?next=%2Fpricing%3Fcheckout%3Dpack%253A1",
      "/signup?next=%2Fpricing%3Fcheckout%3Dpack%253A5",
      "/signup?next=%2Fpricing%3Fcheckout%3Dpack%253A15",
    ]);
    expect(screen.queryByRole("button", { name: /Choose plan/ })).toBeNull();
  });

  it("uses the plan credits from PLANS", () => {
    expect(PLANS.find((p) => p.highlighted)?.credits).toBe(800);
  });
});

describe("CreditPacks", () => {
  beforeEach(() => {
    useCreditsStore.setState({ add: vi.fn(async () => {}), error: null });
    useToastStore.setState({ toasts: [] });
    useAuthStore.setState({ user: { id: "test-user" } as User, loaded: true });
  });
  afterEach(cleanup);

  it("buying a pack posts a pack purchase", async () => {
    const add = vi.fn(async () => {});
    useCreditsStore.setState({ add });
    render(<CreditPacks />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Buy 15 clips" }));
    });
    expect(add).toHaveBeenCalledWith(1500, "pack_purchase", "15");
    expect(useToastStore.getState().toasts.map((t) => t.message)).toEqual(["Added 1,500 credits"]);
  });

  it("offers the first clip until this account has bought it, then hides it", async () => {
    const { unmount } = render(<CreditPacks />);
    expect(screen.getByRole("button", { name: "Buy First clip" })).toBeTruthy();
    expect(screen.getByText("One per account.")).toBeTruthy();
    unmount();
    // useCreditsStore.refresh re-reads the flag from the service, so the state alone is what the page hides on.
    useCreditsStore.setState({ firstClipUsed: true, refresh: vi.fn(async () => {}) });
    render(<CreditPacks />);
    expect(screen.queryByRole("button", { name: "Buy First clip" })).toBeNull();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    useCreditsStore.setState({ firstClipUsed: false });
  });

  it("buying the first clip tells the ledger which pack it was", async () => {
    const add = vi.fn(async () => {});
    useCreditsStore.setState({ add });
    render(<CreditPacks />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Buy First clip" }));
    });
    expect(add).toHaveBeenCalledWith(100, "pack_purchase", "first");
  });

  it("shows a falling per-credit price so the largest pack reads as best value", () => {
    render(<CreditPacks />);
    expect(perCredit(2, 100)).toBe("2.0¢ / credit");
    expect(perCredit(6, 100)).toBe("6.0¢ / credit");
    expect(perCredit(20, 500)).toBe("4.0¢ / credit");
    expect(perCredit(55, 1500)).toBe("3.7¢ / credit");
    expect(screen.getByText(`100 credits · ${perCredit(6, 100)}`)).toBeTruthy();
    expect(screen.getByText(`1,500 credits · ${perCredit(55, 1500)}`)).toBeTruthy();
  });

  it("says what each pack buys, and Finals only on the plans that render them", () => {
    render(<CreditPacks />);
    expect(screen.getAllByText("= 20 Previews, or 1 Final on Creator and Pro")).toHaveLength(2);
    expect(screen.getByText("= 100 Previews, or 5 Finals on Creator and Pro")).toBeTruthy();
    expect(screen.getByText("= 300 Previews, or 15 Finals on Creator and Pro")).toBeTruthy();
    expect(screen.getAllByText("One-time purchase. Pack credits never expire.")).toHaveLength(4);
  });
});

describe("ActionCostTable", () => {
  afterEach(cleanup);

  it("is collapsed by default and lists launch cloud costs when opened", () => {
    render(<ActionCostTable />);
    expect(screen.queryByText(/cheaper than cloud standard/)).toBeNull();
    const toggle = screen.getByRole("button", { name: "See all costs" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggle);
    expect(screen.getByText(/Renders use cloud GPUs at launch/)).toBeTruthy();
    expect(screen.queryByText("Local final render")).toBeNull();
    expect(screen.getByText("Preview render, 540p")).toBeTruthy();
    expect(screen.getByText("Final render, 1080p (Creator and Pro)")).toBeTruthy();
    expect(screen.queryByText(/4K/i)).toBeNull();
  });
});
