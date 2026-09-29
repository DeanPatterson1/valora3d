import { describe, expect, it } from "vitest";
import { CreditReason, type CreditTransaction } from "@/lib/schema";
import {
  HISTORY_PAGE_SIZE,
  historyRowToEntry,
  ledgerLabel,
  localHistory,
  pageRange,
  paginate,
  summariseSubscription,
  toPage,
  type SubscriptionRow,
} from "./history";

describe("ledgerLabel", () => {
  it("says every ledger reason in plain words", () => {
    expect(ledgerLabel({ reason: "render_preview", amount: -3 })).toBe("Preview render");
    expect(ledgerLabel({ reason: "preview_render", amount: -3 })).toBe("Preview render");
    expect(ledgerLabel({ reason: "render_final", amount: -60 })).toBe("Final render");
    expect(ledgerLabel({ reason: "render_refund", amount: 60, jobStatus: "failed" })).toBe("Refund: render failed");
    expect(ledgerLabel({ reason: "render_refund", amount: 60 })).toBe("Refund: render failed");
    expect(ledgerLabel({ reason: "render_refund", amount: 60, jobStatus: "cancelled" })).toBe("Refund: render canceled");
    expect(ledgerLabel({ reason: "pack_purchase", amount: 500 })).toBe("Credit pack 500");
    expect(ledgerLabel({ reason: "pack_purchase", amount: 2000 })).toBe("Credit pack 2,000");
    expect(ledgerLabel({ reason: "plan_grant", amount: 500, plan: "creator" })).toBe("Monthly Creator credits");
    expect(ledgerLabel({ reason: "plan_grant", amount: 2000, plan: "pro" })).toBe("Monthly Pro credits");
    expect(ledgerLabel({ reason: "plan_grant", amount: 2000, plan: null })).toBe("Monthly plan credits");
    expect(ledgerLabel({ reason: "plan_grant", amount: 2000, plan: "<b>" })).toBe("Monthly plan credits");
    expect(ledgerLabel({ reason: "admin_adjustment", amount: 10 })).toBe("Adjustment");
    expect(ledgerLabel({ reason: "billing_reversal", amount: -500 })).toBe("Payment refunded");
    expect(ledgerLabel({ reason: "billing_reversal", amount: 500 })).toBe("Adjustment");
    expect(ledgerLabel({ reason: "signup_grant", amount: 50 })).toBe("Free plan credits");
    expect(ledgerLabel({ reason: "starting_balance", amount: 50 })).toBe("Starting credits");
    expect(ledgerLabel({ reason: "scene_generation", amount: -2 })).toBe("Scene generation");
    expect(ledgerLabel({ reason: "prompt_edit", amount: -1 })).toBe("Prompt edit");
  });

  it("never shows a raw reason code, even for one added later", () => {
    for (const reason of [...CreditReason.options, "signup_grant", "something_new"]) {
      const label = ledgerLabel({ reason, amount: 1 });
      expect(label).not.toMatch(/_/);
      expect(label.length).toBeGreaterThan(3);
    }
    expect(ledgerLabel({ reason: "something_new", amount: 1 })).toBe("Adjustment");
  });
});

describe("pagination", () => {
  it("asks for one look-ahead row per page", () => {
    expect(pageRange(0)).toEqual({ from: 0, to: HISTORY_PAGE_SIZE });
    expect(pageRange(2, 10)).toEqual({ from: 20, to: 30 });
    expect(pageRange(-1, 10)).toEqual({ from: 0, to: 10 });
    expect(pageRange(Number.NaN, 10)).toEqual({ from: 0, to: 10 });
  });

  it("cuts the look-ahead row and reports whether more exist", () => {
    expect(toPage([1, 2, 3], 0, 2)).toEqual({ items: [1, 2], page: 0, hasMore: true });
    expect(toPage([1, 2], 0, 2)).toEqual({ items: [1, 2], page: 0, hasMore: false });
    expect(toPage([], 3, 2)).toEqual({ items: [], page: 3, hasMore: false });
  });

  it("pages an in-memory list the same way", () => {
    const all = Array.from({ length: 45 }, (_, i) => i);
    expect(paginate(all, 0)).toEqual({ items: all.slice(0, 20), page: 0, hasMore: true });
    expect(paginate(all, 1)).toEqual({ items: all.slice(20, 40), page: 1, hasMore: true });
    expect(paginate(all, 2)).toEqual({ items: all.slice(40), page: 2, hasMore: false });
    expect(paginate(all, 3)).toEqual({ items: [], page: 3, hasMore: false });
    expect(paginate(all.slice(0, 20), 0).hasMore).toBe(false);
  });
});

describe("localHistory", () => {
  it("is newest first with the balance after each row", () => {
    const tx = (id: string, amount: number, reason: CreditTransaction["reason"], createdAt: number): CreditTransaction => ({
      id,
      amount,
      reason,
      projectId: null,
      createdAt,
    });
    const h = localHistory([tx("b", -3, "render_preview", 2), tx("a", 50, "starting_balance", 1), tx("c", 500, "pack_purchase", 3)]);
    expect(h.map((e) => [e.id, e.label, e.balanceAfter])).toEqual([
      ["c", "Credit pack 500", 547],
      ["b", "Preview render", 47],
      ["a", "Starting credits", 50],
    ]);
  });
});

describe("historyRowToEntry", () => {
  it("maps a credit_history row", () => {
    expect(
      historyRowToEntry({
        id: 7,
        amount: 60,
        reason: "render_refund",
        project_id: "p",
        created_at: "2026-09-01T00:00:00Z",
        balance_after: 110,
        plan: null,
        job_status: "cancelled",
      }),
    ).toEqual({ id: "7", createdAt: Date.parse("2026-09-01T00:00:00Z"), amount: 60, balanceAfter: 110, label: "Refund: render canceled", projectId: "p" });
  });
});

describe("summariseSubscription", () => {
  const now = Date.parse("2026-09-15T00:00:00Z");
  const sub = (o: Partial<SubscriptionRow>): SubscriptionRow => ({
    plan: "creator",
    status: "active",
    current_period_end: "2026-10-01T00:00:00Z",
    paid_through: "2026-10-01T00:00:00Z",
    canceled_at: null,
    scheduled_change: null,
    ...o,
  });

  it("is null on Free", () => {
    expect(summariseSubscription([], now)).toBeNull();
    expect(summariseSubscription([sub({ status: "canceled", paid_through: "2026-09-01T00:00:00Z" })], now)).toBeNull();
  });

  it("renews an active plan at the period end", () => {
    expect(summariseSubscription([sub({})], now)).toEqual({ plan: "creator", status: "active", next: { kind: "renews", at: Date.parse("2026-10-01T00:00:00Z") } });
  });

  it("ends at a scheduled cancel", () => {
    const s = summariseSubscription([sub({ scheduled_change: { action: "cancel", effective_at: "2026-10-01T00:00:00Z", resume_at: null } })], now);
    expect(s?.next).toEqual({ kind: "ends", at: Date.parse("2026-10-01T00:00:00Z") });
  });

  it("a canceled plan still paid through a future date ends then", () => {
    const s = summariseSubscription([sub({ status: "canceled", paid_through: "2026-09-30T00:00:00Z" })], now);
    expect(s).toEqual({ plan: "creator", status: "canceled", next: { kind: "ends", at: Date.parse("2026-09-30T00:00:00Z") } });
  });

  it("prefers the live subscription over an old lapsing one", () => {
    const s = summariseSubscription(
      [
        sub({ plan: "creator", status: "canceled", paid_through: "2026-09-20T00:00:00Z", current_period_end: "2026-09-20T00:00:00Z" }),
        sub({ plan: "pro", current_period_end: "2026-10-10T00:00:00Z" }),
      ],
      now,
    );
    expect(s?.plan).toBe("pro");
  });
});
