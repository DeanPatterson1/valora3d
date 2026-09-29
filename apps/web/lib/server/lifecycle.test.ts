import { describe, expect, it, vi } from "vitest";
import type { OutgoingEmail } from "@/lib/email/send";
import { runBillingNotices, runLifecycle, type ClaimResult } from "./lifecycle";

const U = (n: number) => `00000000-0000-4000-8000-00000000000${n}`;

/** A fake `rpc` over canned due-lists and a scripted claim_email. */
function fakeDb(opts: {
  due?: Partial<Record<string, unknown[]>>;
  expiry?: unknown[];
  billing?: unknown[];
  claim?: (user: string, kind: string, ref: string) => ClaimResult;
}) {
  const calls: { fn: string; args: Record<string, unknown> }[] = [];
  const rpc = vi.fn(async (fn: string, args: Record<string, unknown> = {}) => {
    calls.push({ fn, args });
    if (fn === "claim_email") return { data: (opts.claim ?? (() => "claimed"))(String(args.p_user_id), String(args.p_kind), String(args.p_ref)), error: null };
    if (fn === "due_lifecycle_emails") return { data: opts.due?.[String(args.p_kind)] ?? [], error: null };
    if (fn === "due_expiry_warnings") return { data: opts.expiry ?? [], error: null };
    if (fn === "due_billing_emails") return { data: opts.billing ?? [], error: null };
    return { data: 1, error: null };
  });
  return { db: { rpc } as never, calls };
}

describe("runLifecycle", () => {
  it("sends each due mail once, with an unsubscribe link for opt-out kinds only", async () => {
    const { db, calls } = fakeDb({
      due: { welcome: [{ user_id: U(1), email: "a@x.co", name: "Ann" }], winback: [{ user_id: U(2), email: "b@x.co", name: "Bo" }] },
      billing: [{ user_id: U(3), email: "c@x.co", name: "Cy", kind: "past_due", ref: "sub_1:20261001", plan: "creator", at: null }],
    });
    const sent: OutgoingEmail[] = [];
    const r = await runLifecycle({ db, send: async (m) => void sent.push(m), unsubscribeSecret: "s", siteUrl: "https://valora3d.com" });
    expect(r.sent).toEqual({ past_due: 1, welcome: 1, winback: 1 });
    expect(sent.map((m) => [m.to, m.category, Boolean(m.unsubscribe)])).toEqual([
      ["c@x.co", "account", false],
      ["a@x.co", "tips", true],
      ["b@x.co", "tips", true],
    ]);
    expect(sent[1].idempotencyKey).toBe(`welcome:${U(1)}:once`);
    expect(calls.filter((c) => c.fn === "claim_email").map((c) => c.args.p_ref)).toEqual(["sub_1:20261001", "once", "once"]);
  });

  it("releases the claim when Resend fails, so the next sweep retries", async () => {
    const { db, calls } = fakeDb({ due: { welcome: [{ user_id: U(1), email: "a@x.co", name: "A" }] } });
    const r = await runLifecycle({ db, send: async () => { throw new Error("503"); }, unsubscribeSecret: "s" });
    expect(r.failed).toBe(1);
    expect(calls.find((c) => c.fn === "release_email")?.args).toEqual({ p_user_id: U(1), p_kind: "welcome", p_ref: "once" });
  });

  it("skips what claim_email refuses and never sends it", async () => {
    const { db } = fakeDb({
      due: { tips: [{ user_id: U(1), email: "a@x.co", name: "A" }, { user_id: U(2), email: "b@x.co", name: "B" }] },
      claim: (u) => (u === U(1) ? "opted_out" : "rate_limited"),
    });
    const send = vi.fn();
    const r = await runLifecycle({ db, send, unsubscribeSecret: "s" });
    expect(send).not.toHaveBeenCalled();
    expect(r).toMatchObject({ skipped: 1, held: 1, failed: 0 });
  });

  it("expiry: one mail per user per day, jobs marked unless held back", async () => {
    const row = (n: number) => ({ user_id: U(n), email: `${n}@x.co`, name: "", plan: "free", job_ids: [`j${n}a`, `j${n}b`], first_expiry: "2026-10-04T00:00:00Z", render_count: 2, retention_days: 7 });
    const { db, calls } = fakeDb({ expiry: [row(1), row(2), row(3)], claim: (u) => (u === U(2) ? "rate_limited" : u === U(3) ? "suppressed" : "claimed") });
    const sent: OutgoingEmail[] = [];
    await runLifecycle({ db, send: async (m) => void sent.push(m), unsubscribeSecret: "s", now: new Date("2026-10-01T09:00:00Z") });
    expect(sent).toHaveLength(1);
    expect(sent[0].subject).toBe("2 renders will be deleted on October 4, 2026");
    expect(calls.find((c) => c.fn === "claim_email")?.args.p_ref).toBe("2026-10-01");
    expect(calls.filter((c) => c.fn === "mark_expiry_warned").map((c) => c.args.p_job_ids)).toEqual([["j1a", "j1b"], ["j3a", "j3b"]]);
  });

  it("stops at the send budget", async () => {
    const many = Array.from({ length: 5 }, (_, i) => ({ user_id: U(i), email: `${i}@x.co`, name: "" }));
    const { db } = fakeDb({ due: { welcome: many, tips: many } });
    const send = vi.fn(async () => {});
    await runLifecycle({ db, send, unsubscribeSecret: "s", budget: 3 });
    expect(send).toHaveBeenCalledTimes(3);
  });

  it("runBillingNotices narrows to one account", async () => {
    const { db, calls } = fakeDb({ billing: [] });
    await runBillingNotices({ db, send: vi.fn(), unsubscribeSecret: "s" }, U(4));
    expect(calls[0]).toEqual({ fn: "due_billing_emails", args: { p_user_id: U(4), p_limit: 40 } });
  });
});
