import { describe, expect, it, vi } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import { SupabaseAccountService } from "./account";

/** A tiny PostgREST query-builder fake that records the calls and resolves with `result`. */
function fakeDb(result: { data: unknown; error: unknown }) {
  const calls: [string, unknown[]][] = [];
  const builder: Record<string, unknown> = {};
  for (const m of ["from", "select", "order", "range", "limit"]) {
    builder[m] = (...args: unknown[]) => {
      calls.push([m, args]);
      return builder;
    };
  }
  builder.then = (resolve: (v: unknown) => void) => resolve(result);
  return { db: () => builder as unknown as SupabaseClient, calls };
}

describe("SupabaseAccountService", () => {
  it("reads one page of credit_history newest first with a look-ahead row", async () => {
    const rows = Array.from({ length: 21 }, (_, i) => ({
      id: 100 - i,
      amount: -3,
      reason: "render_preview",
      project_id: null,
      created_at: "2026-09-01T00:00:00Z",
      balance_after: 500 - i * 3,
      plan: null,
      job_status: null,
    }));
    const { db, calls } = fakeDb({ data: rows, error: null });
    const r = await new SupabaseAccountService(db).creditHistory(1);
    expect(calls).toContainEqual(["from", ["credit_history"]]);
    expect(calls).toContainEqual(["order", ["id", { ascending: false }]]);
    expect(calls).toContainEqual(["range", [20, 40]]);
    expect(r.ok && r.value.items.length).toBe(20);
    expect(r.ok && r.value.hasMore).toBe(true);
    expect(r.ok && r.value.items[0]?.label).toBe("Preview render");
  });

  it("maps a database error to a friendly failure", async () => {
    const { db } = fakeDb({ data: null, error: { message: "boom", code: "XX000" } });
    const r = await new SupabaseAccountService(db).creditHistory(0);
    expect(r.ok).toBe(false);
  });

  it("summarises the user's own subscription rows", async () => {
    const { db, calls } = fakeDb({
      data: [{ plan: "pro", status: "active", current_period_end: "2099-01-01T00:00:00Z", paid_through: null, canceled_at: null, scheduled_change: null }],
      error: null,
    });
    const r = await new SupabaseAccountService(db).subscription();
    expect(calls).toContainEqual(["from", ["billing_subscriptions"]]);
    expect(r.ok && r.value?.next?.kind).toBe("renews");
  });

  it("asks the server route for renders (posters are presigned server-side)", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ items: [], page: 2, hasMore: false }));
    const { db } = fakeDb({ data: [], error: null });
    const r = await new SupabaseAccountService(db, fetchImpl as unknown as typeof fetch).renders(2);
    expect((fetchImpl.mock.calls[0] as unknown as [string])[0]).toBe("/api/account/renders?page=2");
    expect(r.ok && r.value.page).toBe(2);
  });
});
