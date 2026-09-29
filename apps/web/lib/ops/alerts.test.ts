// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { alertsFrom, digestEmail, sendOwnerMail, type AlertSignals, type Digest } from "./alerts";
import { runAlerts, runDigest } from "./run";

const quiet: AlertSignals = {
  worker_misconfigured: 0,
  recent: { finished: 20, failed: 2 },
  webhook_errors: 0,
  gpu_seconds_today: "1200.0",
  daily_gpu_budget_seconds: null,
  active_renders: 1,
  global_max_active_renders: null,
};

const DIGEST: Digest = {
  since: "2026-09-29T07:00:00Z",
  until: "2026-09-30T07:00:00Z",
  signups: 12,
  renders: { total: 40, succeeded: 35, failed: 3, cancelled: 2, in_flight: 0, gpu_seconds: "21600.0", cost_usd: "6.61" },
  failures_by_code: { WORKER_MISCONFIGURED: 2, GLB_INVALID: 1 },
  refunds: { render_credits: 9, billing_adjustments: 1 },
  revenue: [{ currency: "USD", gross_minor: 4900, transactions: 2 }],
  webhook_errors: 0,
  client_errors: 4,
  paused: ["finals_enabled"],
};

describe("owner alerts", () => {
  it("stays quiet on a healthy system", () => {
    expect(alertsFrom(quiet)).toEqual([]);
  });

  it("alerts on a misconfigured worker, a failure rate over 20%, webhook errors and a spent budget", () => {
    const kinds = alertsFrom({
      ...quiet,
      worker_misconfigured: 1,
      recent: { finished: 20, failed: 5 },
      webhook_errors: 2,
      gpu_seconds_today: 3600,
      daily_gpu_budget_seconds: "3600",
    }).map((a) => a.kind);
    expect(kinds).toEqual(["worker_misconfigured", "failure_rate", "billing_webhook_errors", "budget_tripped"]);
  });

  it("needs five finished renders before a failure rate counts, and exactly 20% is not an alert", () => {
    expect(alertsFrom({ ...quiet, recent: { finished: 4, failed: 4 } })).toEqual([]);
    expect(alertsFrom({ ...quiet, recent: { finished: 20, failed: 4 } })).toEqual([]);
  });

  it("writes a plain digest with aggregates only", () => {
    const mail = digestEmail(DIGEST, "2026-09-30");
    expect(mail.subject).toBe("Valora3D daily: 12 signups, 35 renders, 3 failed (2026-09-30)");
    expect(mail.text).toContain("GPU time: 6.00 h, est. $6.61");
    expect(mail.text).toContain("Failures by code: WORKER_MISCONFIGURED 2, GLB_INVALID 1");
    expect(mail.text).toContain("Revenue: USD 49.00 (2)");
    expect(mail.text).toContain("Switched OFF: finals_enabled");
    expect(mail.text).not.toMatch(/@/);
  });

  it("claims each alert kind before mailing it, so one mail per kind per hour", async () => {
    const claims = new Set<string>();
    const rpc = vi.fn(async (fn: string, args?: Record<string, unknown>) => {
      if (fn === "ops_alert_signals") return { data: { ...quiet, worker_misconfigured: 3, webhook_errors: 1 }, error: null };
      if (fn === "claim_owner_alert") {
        const kind = String(args?.p_kind);
        const fresh = !claims.has(kind);
        claims.add(kind);
        return { data: fresh, error: null };
      }
      return { data: null, error: { message: "unexpected" } };
    });
    const send = vi.fn(async () => {});
    expect(await runAlerts({ rpc } as never, send)).toEqual({
      alerts: ["worker_misconfigured", "billing_webhook_errors"],
      sent: ["worker_misconfigured", "billing_webhook_errors"],
    });
    expect((await runAlerts({ rpc } as never, send)).sent).toEqual([]);
    expect(send).toHaveBeenCalledTimes(2);
    // Without mail configured, alerts are reported but not claimed.
    claims.clear();
    expect(await runAlerts({ rpc } as never, null)).toEqual({ alerts: ["worker_misconfigured", "billing_webhook_errors"], sent: [] });
    expect(claims.size).toBe(0);
  });

  it("sends the digest once a day", async () => {
    let claimed = false;
    const rpc = vi.fn(async (fn: string) => {
      if (fn === "claim_owner_alert") {
        const first = !claimed;
        claimed = true;
        return { data: first, error: null };
      }
      return { data: DIGEST, error: null };
    });
    const send = vi.fn(async () => {});
    expect(await runDigest({ rpc } as never, send, new Date("2026-09-30T07:00:00Z"))).toEqual({ sent: true });
    expect(await runDigest({ rpc } as never, send)).toEqual({ sent: false, reason: "already sent today" });
    expect(send).toHaveBeenCalledWith(expect.objectContaining({ subject: expect.stringContaining("12 signups") }), "digest-2026-09-30");
    expect(await runDigest({ rpc } as never, null)).toEqual({ sent: false, reason: "mail not configured" });
  });

  it("sends through Resend with an idempotency key, text only", async () => {
    const fetchImpl = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response("{}", { status: 200 }));
    await sendOwnerMail({ resendApiKey: "re_x", from: "Valora3D <ops@valora3d.com>", to: "owner@example.com" }, { subject: "s", text: "t" }, "alert-x", fetchImpl as never);
    const init = fetchImpl.mock.calls[0][1]!;
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("alert-x");
    expect(JSON.parse(String(init.body))).toEqual({ from: "Valora3D <ops@valora3d.com>", to: ["owner@example.com"], subject: "s", text: "t" });
    const failing = vi.fn(async () => new Response("", { status: 500 }));
    await expect(sendOwnerMail({ resendApiKey: "k", from: "f", to: "t@x.io" }, { subject: "s", text: "t" }, "k", failing as never)).rejects.toThrow("500");
  });
});
