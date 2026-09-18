// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CREDIT_COSTS, PLANS } from "@/lib/pricing";
import { useCreditsStore } from "@/lib/stores/credits";
import { useToastStore } from "@/components/ui/Toast";
import { ActionCostTable, LOCAL_VS_CLOUD } from "./ActionCostTable";
import { CreditPacks, perCredit } from "./CreditPacks";
import { PlanCards } from "./PlanCards";

describe("PlanCards", () => {
  beforeEach(() => {
    useCreditsStore.setState({ add: vi.fn(async () => {}), error: null });
    useToastStore.setState({ toasts: [] });
  });
  afterEach(cleanup);

  it("renders three plans with Creator highlighted", () => {
    render(<PlanCards />);
    const list = screen.getByRole("list", { name: "Plans" });
    const cards = within(list).getAllByRole("listitem").filter((li) => li.hasAttribute("data-plan"));
    expect(cards.map((c) => c.getAttribute("data-plan"))).toEqual(["Free", "Creator", "Pro"]);
    expect(cards.filter((c) => c.hasAttribute("data-highlighted")).map((c) => c.getAttribute("data-plan"))).toEqual(["Creator"]);
    expect(within(cards[1]).getByText("Most popular")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^Choose plan/ })).toHaveLength(3);
  });

  it("choosing Creator adds 500 credits as a plan grant and toasts", async () => {
    const add = vi.fn(async () => {});
    useCreditsStore.setState({ add });
    render(<PlanCards />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Choose plan: Creator" }));
    });
    expect(add).toHaveBeenCalledWith(500, "plan_grant");
    expect(useToastStore.getState().toasts.map((t) => t.message)).toEqual(["Added 500 credits (prototype)"]);
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

  it("uses the plan credits from PLANS", () => {
    expect(PLANS.find((p) => p.highlighted)?.credits).toBe(500);
  });
});

describe("CreditPacks", () => {
  beforeEach(() => {
    useCreditsStore.setState({ add: vi.fn(async () => {}), error: null });
    useToastStore.setState({ toasts: [] });
  });
  afterEach(cleanup);

  it("buying a pack posts a pack purchase", async () => {
    const add = vi.fn(async () => {});
    useCreditsStore.setState({ add });
    render(<CreditPacks />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Buy 2,000 credits" }));
    });
    expect(add).toHaveBeenCalledWith(2000, "pack_purchase");
    expect(useToastStore.getState().toasts.map((t) => t.message)).toEqual(["Added 2,000 credits (prototype)"]);
  });

  it("shows a falling per-credit price so the largest pack reads as best value", () => {
    render(<CreditPacks />);
    expect(screen.getByText(perCredit(5, 100))).toBeTruthy();
    expect(perCredit(5, 100)).toBe("5.0¢ / credit");
    expect(perCredit(70, 2000)).toBe("3.5¢ / credit");
  });
});

describe("ActionCostTable", () => {
  afterEach(cleanup);

  it("is collapsed by default and shows the 6x local-vs-cloud callout when opened", () => {
    render(<ActionCostTable />);
    expect(screen.queryByText(/cheaper than cloud standard/)).toBeNull();
    const toggle = screen.getByRole("button", { name: "See all costs" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggle);
    expect(LOCAL_VS_CLOUD).toBe(CREDIT_COSTS.cloud_final.standard / CREDIT_COSTS.local_final);
    expect(screen.getByText(/Local rendering is 6× cheaper than cloud standard/)).toBeTruthy();
    expect(screen.getByText("Local final render")).toBeTruthy();
    expect(screen.getByText("Cloud final render, 4K")).toBeTruthy();
  });
});
