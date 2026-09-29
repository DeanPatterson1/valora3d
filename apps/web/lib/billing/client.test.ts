// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { planAction } from "@/components/pricing/PlanCards";
import { onPaddleEvent, openBillingPortal, resetPaddleLoader, startCheckout, type PaddleGlobal } from "./client";

const config = { clientToken: "test_client_token", environment: "sandbox" as const };

function fakePaddle() {
  return { Environment: { set: vi.fn() }, Initialize: vi.fn(), Checkout: { open: vi.fn() } } satisfies PaddleGlobal;
}

afterEach(() => {
  resetPaddleLoader();
  delete window.Paddle;
});

describe("startCheckout", () => {
  it("asks the server for the item and opens the overlay with the server's price and custom data", async () => {
    const paddle = fakePaddle();
    const fetchImpl = vi.fn(async () => Response.json({
      kind: "checkout", priceId: "pri_pack500", customData: { user_id: "u", user_sig: "s" }, customerId: null, customerEmail: "a@example.com",
    }));
    const r = await startCheckout("pack:600", { config, fetchImpl: fetchImpl as unknown as typeof fetch, load: async () => paddle });
    expect(r).toEqual({ ok: true, value: "opened" });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/billing/checkout");
    // The browser sends only the catalog key: no price, no amount.
    expect(JSON.parse(init.body as string)).toEqual({ item: "pack:600" });
    expect(paddle.Checkout.open).toHaveBeenCalledWith(expect.objectContaining({
      items: [{ priceId: "pri_pack500", quantity: 1 }],
      customer: { email: "a@example.com" },
      customData: { user_id: "u", user_sig: "s" },
    }));
  });

  it("prefers the server's Paddle customer id over the email", async () => {
    const paddle = fakePaddle();
    const fetchImpl = vi.fn(async () => Response.json({
      kind: "checkout", priceId: "pri_x", customData: { user_id: "u", user_sig: "s" }, customerId: "ctm_mine", customerEmail: "a@example.com",
    }));
    await startCheckout("pack:250", { config, fetchImpl: fetchImpl as unknown as typeof fetch, load: async () => paddle });
    expect(paddle.Checkout.open).toHaveBeenCalledWith(expect.objectContaining({ customer: { id: "ctm_mine" } }));
  });

  it("reports a plan change without opening checkout", async () => {
    const load = vi.fn();
    const fetchImpl = vi.fn(async () => Response.json({ kind: "changed" }));
    expect(await startCheckout("plan:pro", { config, fetchImpl: fetchImpl as unknown as typeof fetch, load }))
      .toEqual({ ok: true, value: "changed" });
    expect(load).not.toHaveBeenCalled();
  });

  it("is closed without a client token, and surfaces server errors", async () => {
    expect(await startCheckout("pack:250", { config: null })).toMatchObject({ ok: false, error: { code: "checkout_unavailable" } });
    const fetchImpl = vi.fn(async () => Response.json({ error: { code: "already_subscribed", message: "You're already on this plan." } }, { status: 409 }));
    expect(await startCheckout("plan:creator", { config, fetchImpl: fetchImpl as unknown as typeof fetch }))
      .toEqual({ ok: false, error: { code: "already_subscribed", message: "You're already on this plan." } });
  });

  it("initialises Paddle.js once, in sandbox, and forwards its events", async () => {
    const paddle = fakePaddle();
    window.Paddle = paddle;
    const events: string[] = [];
    onPaddleEvent((e) => events.push(e.name ?? ""));
    const fetchImpl = vi.fn(async () => Response.json({ kind: "checkout", priceId: "pri_x", customData: { user_id: "u", user_sig: "s" }, customerId: null, customerEmail: null }));
    await startCheckout("pack:250", { config, fetchImpl: fetchImpl as unknown as typeof fetch });
    await startCheckout("pack:250", { config, fetchImpl: fetchImpl as unknown as typeof fetch });
    expect(paddle.Environment.set).toHaveBeenCalledWith("sandbox");
    expect(paddle.Initialize).toHaveBeenCalledTimes(1);
    const { eventCallback } = paddle.Initialize.mock.calls[0][0] as { eventCallback: (e: { name: string }) => void };
    eventCallback({ name: "checkout.completed" });
    expect(events).toEqual(["checkout.completed"]);
  });
});

describe("openBillingPortal", () => {
  it("navigates to the portal link from the server", async () => {
    const navigate = vi.fn();
    const fetchImpl = vi.fn(async () => Response.json({ url: "https://customer-portal.paddle.com/cpl_1" }));
    expect(await openBillingPortal({ fetchImpl: fetchImpl as unknown as typeof fetch, navigate })).toEqual({ ok: true, value: undefined });
    expect(navigate).toHaveBeenCalledWith("https://customer-portal.paddle.com/cpl_1");
  });
});

describe("planAction", () => {
  it("keeps the local prototype's grant buttons", () => {
    expect(planAction("local", "pro", "pro")).toBe("choose");
  });
  it("marks the current plan and points paying users at billing for Free", () => {
    expect(planAction("supabase", "creator", "creator")).toBe("current");
    expect(planAction("supabase", "pro", "creator")).toBe("choose");
    expect(planAction("supabase", "free", "pro")).toBe("manage");
    expect(planAction("supabase", "free", "free")).toBe("current");
  });
});
