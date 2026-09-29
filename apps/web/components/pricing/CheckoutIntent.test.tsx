// @vitest-environment jsdom
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { User } from "@/lib/schema";
import { useAuthStore } from "@/lib/stores/auth";
import { useCreditsStore } from "@/lib/stores/credits";
import { useToastStore } from "@/components/ui/Toast";
import { CheckoutIntent, intentAction } from "./CheckoutIntent";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(search),
  usePathname: () => "/pricing",
}));

beforeEach(() => {
  replace.mockClear();
  search = "";
  useToastStore.setState({ toasts: [] });
});
afterEach(cleanup);

describe("intentAction", () => {
  it("opens checkout for a plan you can buy, never for the one you have", () => {
    expect(intentAction("supabase", "plan:creator", "free")).toBe("checkout");
    expect(intentAction("supabase", "plan:creator", "creator")).toBe("none");
    expect(intentAction("supabase", "pack:5", "pro")).toBe("checkout");
    expect(intentAction("local", "plan:pro", "free")).toBe("grant");
  });
});

describe("CheckoutIntent (/pricing?checkout=<item>, the end of 'chose a plan, then signed up')", () => {
  it("runs the chosen item once for a signed-in user and drops the parameter", async () => {
    const add = vi.fn(async () => {});
    useCreditsStore.setState({ add, error: null });
    useAuthStore.setState({ user: { id: "u", plan: "free" } as User, loaded: true });
    search = "checkout=plan%3Acreator";
    const { rerender } = render(<CheckoutIntent />);
    await act(async () => {});
    rerender(<CheckoutIntent />);
    await act(async () => {});
    // Local mode's checkout is a grant; the real backend opens Paddle through the same useCheckout as the cards.
    expect(add).toHaveBeenCalledTimes(1);
    expect(add).toHaveBeenCalledWith(800, "plan_grant", undefined);
    expect(replace).toHaveBeenCalledWith("/pricing", { scroll: false });
  });

  it("waits for sign-in, and ignores anything that is not a catalog item", async () => {
    const add = vi.fn(async () => {});
    useCreditsStore.setState({ add, error: null });
    useAuthStore.setState({ user: null, loaded: true, refresh: async () => {} });
    search = "checkout=pack%3A600";
    render(<CheckoutIntent />);
    await act(async () => {});
    expect(add).not.toHaveBeenCalled();
    cleanup();

    useAuthStore.setState({ user: { id: "u", plan: "free" } as User, loaded: true });
    search = "checkout=pack%3A999999";
    render(<CheckoutIntent />);
    await act(async () => {});
    expect(add).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });
});
