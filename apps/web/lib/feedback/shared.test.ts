import { describe, expect, it } from "vitest";
import { offersFor, pauseResumeAt } from "@/lib/billing/cancel";
import { buildExport, EXPORT_TABLES } from "@/lib/server/dataExport";
import { FeedbackRequest, feedbackIntent, feedbackRow } from "./shared";

describe("feedback", () => {
  it("keeps only a route template, a clean release and a browser family", () => {
    const body = FeedbackRequest.parse({ kind: "bug", message: "  It broke  ", page: "/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f?x=1", release: "a1b2c3d" });
    expect(feedbackRow(body, "chrome_mobile")).toEqual({ kind: "bug", message: "It broke", page: "/projects/[id]", release: "a1b2c3d", ua_family: "chrome_mobile" });
    expect(feedbackRow({ ...body, release: "bad release!" }, "Chrome 1.0").release).toBeNull();
    expect(feedbackRow({ ...body, release: "bad release!" }, "Chrome 1.0").ua_family).toBeNull();
  });
  it("refuses empty, oversized or unknown input", () => {
    expect(FeedbackRequest.safeParse({ kind: "bug", message: " a " }).success).toBe(false);
    expect(FeedbackRequest.safeParse({ kind: "bug", message: "x".repeat(4001) }).success).toBe(false);
    expect(FeedbackRequest.safeParse({ kind: "rant", message: "hello" }).success).toBe(false);
    expect(FeedbackRequest.safeParse({ kind: "bug", message: "hello", email: "x" }).success).toBe(false);
  });
  it("reads ?feedback= and ?from= from an error page link", () => {
    const p = (q: string) => new URLSearchParams(q);
    expect(feedbackIntent(p(""))).toBeNull();
    expect(feedbackIntent(p("feedback=idea"))).toEqual({ kind: "idea", from: null });
    expect(feedbackIntent(p("feedback=zzz&from=/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f"))).toEqual({ kind: "bug", from: "/projects/[id]" });
    expect(feedbackIntent(p("feedback=bug&from=https://evil.example"))).toEqual({ kind: "bug", from: null });
  });
});

describe("cancel offers", () => {
  it("offers Creator only from Pro when on sale, and a pause only while active", () => {
    expect(offersFor({ plan: "pro", status: "active" }, true)).toEqual(["downgrade", "pause"]);
    expect(offersFor({ plan: "pro", status: "active" }, false)).toEqual(["pause"]);
    expect(offersFor({ plan: "creator", status: "active" }, true)).toEqual(["pause"]);
    expect(offersFor({ plan: "creator", status: "past_due" }, true)).toEqual([]);
  });
  it("a pause resumes 30 days after the period ends", () => {
    expect(pauseResumeAt(new Date("2026-10-28T00:00:00Z")).toISOString()).toBe("2026-11-27T00:00:00.000Z");
  });
});

describe("data export", () => {
  it("reads users' own tables with their session and the three private ones by their id only", async () => {
    const userTables: string[] = [];
    const service: [string, string | undefined][] = [];
    const doc = await buildExport(
      "u1",
      async () => ({ data: { email: "a@x.co", name: "Ann", plan: "free", created_at: "2026-09-01", prefs: { a: 1 }, email_product_tips: false }, error: null }),
      async (t) => {
        userTables.push(t);
        return { data: [{ t }], error: null };
      },
      async (t, _c, by) => {
        service.push([t, by]);
        return { data: [], error: null };
      },
      new Date("2026-10-01T00:00:00Z"),
    );
    expect(userTables).toEqual(EXPORT_TABLES.filter((t) => !t.service).map((t) => t.table));
    expect(service).toEqual([["feedback", "u1"], ["cancellation_feedback", "u1"], ["email_log", "u1"]]);
    expect(doc).toMatchObject({
      format: "valora3d-export/v1",
      account: { id: "u1", email: "a@x.co" },
      preferences: { settings: { a: 1 }, email_product_tips: false, email_render_notifications: true },
      projects: [{ t: "projects" }],
    });
    expect(JSON.stringify(doc)).not.toMatch(/r2_key|paddle_customer/);
  });
  it("fails whole rather than exporting a partial file", async () => {
    await expect(
      buildExport("u1", async () => ({ data: {}, error: null }), async () => ({ data: null, error: { message: "x" } }), async () => ({ data: [], error: null })),
    ).rejects.toThrow();
  });
});
