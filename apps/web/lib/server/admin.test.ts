// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { retryKey } from "@/lib/admin/types";
import { handleWebhook } from "@/lib/billing/webhook";
import { signPaddlePayload } from "@/lib/billing/signature";
import { isAdminPath, isAdminUser } from "@/lib/supabase/proxy";
import { ADMIN_SECTIONS, sectionFor } from "@/components/admin/AdminShell";

/**
 * Authorization and idempotency of the admin console's API. The database side (admin_* functions: replays,
 * audit rows, RLS) is pinned by supabase/tests/admin_console.test.sql; here the routes are run against a fake
 * service-role client so every route's gate and every action's request id is checked without a network.
 */

const ADMIN_ID = "0d0d0d0d-aaaa-4bbb-8ccc-dddddddddddd";
const USER_ID = "3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f";
const JOB_ID = "a1b2c3d4-0000-4000-8000-000000000002";

type Result = { data: unknown; error: { code?: string; message: string } | null };

const h = vi.hoisted(() => ({
  session: null as null | { id: string },
  admins: new Set<string>(),
  tables: {} as Record<string, unknown>,
  rpc: vi.fn(),
  create: vi.fn(),
}));

/** A chainable stand-in for the service-role client: every filter returns itself; awaiting gives the table's rows. */
function fakeClient() {
  return {
    from(table: string) {
      const filters: Record<string, unknown> = {};
      const result = (): Result => {
        if (table === "admins") return { data: h.admins.has(String(filters.user_id)) ? { user_id: filters.user_id } : null, error: null };
        return { data: h.tables[table] ?? null, error: null };
      };
      const builder = {
        select: () => builder,
        eq: (k: string, v: unknown) => ((filters[k] = v), builder),
        in: () => builder,
        lt: () => builder,
        order: () => builder,
        limit: () => builder,
        maybeSingle: async () => result(),
        then: (resolve: (r: Result) => unknown) => resolve({ data: h.tables[table] ?? [], error: null }),
      };
      return builder;
    },
    rpc: (name: string, args?: unknown) => h.rpc(name, args),
  };
}

vi.mock("@/lib/supabase/server", () => ({
  apiError: (status: number, code: string, message: string) => Response.json({ error: { code, message } }, { status }),
  createServiceSupabase: () => fakeClient(),
  requireUser: async () =>
    h.session
      ? { config: { supabase: { url: "u", anonKey: "a", serviceRoleKey: "s" } }, user: h.session, userClient: fakeClient() }
      : Response.json({ error: { code: "unauthorized" } }, { status: 401 }),
}));
vi.mock("@/lib/server/renderContext", () => ({ createRenderPipeline: () => ({ create: h.create }) }));

const overview = await import("@/app/api/admin/overview/route");
const renders = await import("@/app/api/admin/renders/route");
const render = await import("@/app/api/admin/renders/[id]/route");
const retry = await import("@/app/api/admin/renders/[id]/retry/route");
const refund = await import("@/app/api/admin/renders/[id]/refund/route");
const users = await import("@/app/api/admin/users/route");
const user = await import("@/app/api/admin/users/[id]/route");
const credits = await import("@/app/api/admin/users/[id]/credits/route");
const billing = await import("@/app/api/admin/billing/route");
const audit = await import("@/app/api/admin/audit/route");

const ORIGIN = "https://valora3d.com";
const get = (path: string) => new Request(`${ORIGIN}${path}`);
const post = (path: string, body: unknown, origin = ORIGIN) =>
  new Request(`${ORIGIN}${path}`, { method: "POST", headers: { origin, "content-type": "application/json" }, body: JSON.stringify(body) });
const ctx = (id: string) => ({ params: Promise.resolve({ id }) });

/** Every admin route, called the way Next calls it. */
const ROUTES: [string, () => Promise<Response>][] = [
  ["GET /api/admin/overview", () => overview.GET()],
  ["GET /api/admin/renders", () => renders.GET(get("/api/admin/renders"))],
  ["GET /api/admin/renders/:id", () => render.GET(get(`/api/admin/renders/${JOB_ID}`), ctx(JOB_ID))],
  ["POST /api/admin/renders/:id/retry", () => retry.POST(post(`/api/admin/renders/${JOB_ID}/retry`, {}), ctx(JOB_ID))],
  ["POST /api/admin/renders/:id/refund", () => refund.POST(post(`/api/admin/renders/${JOB_ID}/refund`, { reason: "our fault", request_id: "req12345678" }), ctx(JOB_ID))],
  ["GET /api/admin/users", () => users.GET(get("/api/admin/users?q=a"))],
  ["GET /api/admin/users/:id", () => user.GET(get(`/api/admin/users/${USER_ID}`), ctx(USER_ID))],
  ["POST /api/admin/users/:id/credits", () => credits.POST(post(`/api/admin/users/${USER_ID}/credits`, { amount: 10, reason: "goodwill", request_id: "req12345678" }), ctx(USER_ID))],
  ["GET /api/admin/billing", () => billing.GET()],
  ["GET /api/admin/audit", () => audit.GET(get("/api/admin/audit"))],
];

const failedJob = {
  id: JOB_ID,
  user_id: USER_ID,
  project_id: "11111111-2222-4333-8444-555555555555",
  upload_id: "99999999-8888-4777-8666-555555555555",
  version_id: null,
  kind: "preview",
  status: "failed",
  retryable: true,
  params: { prompt: "orbit", tier: "preview" },
  cost_credits: 3,
  refunded_credits: 3,
};

beforeEach(() => {
  h.session = null;
  h.admins = new Set([ADMIN_ID]);
  h.tables = {};
  h.rpc.mockReset();
  h.create.mockReset();
  h.rpc.mockResolvedValue({ data: {}, error: null });
});
afterEach(() => vi.restoreAllMocks());

describe("admin API authorization", () => {
  it.each(ROUTES)("%s answers 403 when signed out", async (_name, call) => {
    const res = await call();
    expect(res.status).toBe(403);
    expect(h.rpc).not.toHaveBeenCalled();
    expect(h.create).not.toHaveBeenCalled();
  });

  it.each(ROUTES)("%s answers 403 to a signed-in non-admin", async (_name, call) => {
    h.session = { id: USER_ID };
    const res = await call();
    expect(res.status).toBe(403);
    expect(await res.json()).toEqual({ error: { code: "forbidden", message: "Forbidden." } });
    expect(h.rpc).not.toHaveBeenCalled();
    expect(h.create).not.toHaveBeenCalled();
  });

  it("lets an admin through, uncached and unindexed", async () => {
    h.session = { id: ADMIN_ID };
    h.rpc.mockResolvedValue({ data: { signups: {} }, error: null });
    const res = await overview.GET();
    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(res.headers.get("x-robots-tag")).toBe("noindex, nofollow");
    expect(h.rpc).toHaveBeenCalledWith("admin_overview", undefined);
  });

  it("refuses cross-origin admin actions even from an admin", async () => {
    h.session = { id: ADMIN_ID };
    const res = await credits.POST(post(`/api/admin/users/${USER_ID}/credits`, { amount: 10, reason: "goodwill", request_id: "req12345678" }, "https://evil.example"), ctx(USER_ID));
    expect(res.status).toBe(403);
    expect(h.rpc).not.toHaveBeenCalled();
  });
});

describe("credit adjustments", () => {
  beforeEach(() => {
    h.session = { id: ADMIN_ID };
  });

  it("sends the admin id, the reason and a namespaced request id to admin_adjust_credits", async () => {
    h.rpc.mockResolvedValue({ data: { replay: false, balance: 60 }, error: null });
    const res = await credits.POST(post(`/api/admin/users/${USER_ID}/credits`, { amount: -10, reason: "  clawback  ", request_id: "req12345678" }), ctx(USER_ID));
    expect(res.status).toBe(200);
    expect(h.rpc).toHaveBeenCalledWith("admin_adjust_credits", {
      p_admin_id: ADMIN_ID,
      p_user_id: USER_ID,
      p_amount: -10,
      p_reason: "clawback",
      p_request_id: "credits:req12345678",
    });
  });

  it("sends a repeated click with the same request id, so the database applies it once", async () => {
    h.rpc.mockResolvedValueOnce({ data: { replay: false, balance: 60 }, error: null }).mockResolvedValueOnce({ data: { replay: true, balance: 60 }, error: null });
    const body = { amount: 10, reason: "goodwill", request_id: "req12345678" };
    await credits.POST(post(`/api/admin/users/${USER_ID}/credits`, body), ctx(USER_ID));
    const again = await credits.POST(post(`/api/admin/users/${USER_ID}/credits`, body), ctx(USER_ID));
    expect(await again.json()).toEqual({ result: { replay: true, balance: 60 } });
    expect(h.rpc.mock.calls.map((c) => (c[1] as { p_request_id: string }).p_request_id)).toEqual(["credits:req12345678", "credits:req12345678"]);
  });

  it.each([
    ["a zero amount", { amount: 0, reason: "goodwill", request_id: "req12345678" }],
    ["a fractional amount", { amount: 1.5, reason: "goodwill", request_id: "req12345678" }],
    ["a missing reason", { amount: 5, reason: "  ", request_id: "req12345678" }],
    ["a missing request id", { amount: 5, reason: "goodwill" }],
    ["an oversized grant", { amount: 1_000_000, reason: "goodwill", request_id: "req12345678" }],
  ])("rejects %s before the database", async (_name, body) => {
    const res = await credits.POST(post(`/api/admin/users/${USER_ID}/credits`, body), ctx(USER_ID));
    expect(res.status).toBe(400);
    expect(h.rpc).not.toHaveBeenCalled();
  });

  it("maps a reused request id to 409 and a demoted admin to 403", async () => {
    h.rpc.mockResolvedValueOnce({ data: null, error: { code: "23505", message: "request id reused with different details" } });
    expect((await credits.POST(post(`/api/admin/users/${USER_ID}/credits`, { amount: 5, reason: "goodwill", request_id: "req12345678" }), ctx(USER_ID))).status).toBe(409);
    h.rpc.mockResolvedValueOnce({ data: null, error: { code: "42501", message: "not an admin" } });
    expect((await credits.POST(post(`/api/admin/users/${USER_ID}/credits`, { amount: 5, reason: "goodwill", request_id: "req12345679" }), ctx(USER_ID))).status).toBe(403);
  });
});

describe("render refunds", () => {
  beforeEach(() => {
    h.session = { id: ADMIN_ID };
  });

  it("goes through admin_refund_render_job with the admin and request id", async () => {
    h.rpc.mockResolvedValue({ data: { replay: false, refunded: 3 }, error: null });
    const res = await refund.POST(post(`/api/admin/renders/${JOB_ID}/refund`, { reason: "GPU crash", request_id: "req12345678" }), ctx(JOB_ID));
    expect(await res.json()).toEqual({ result: { replay: false, refunded: 3 } });
    expect(h.rpc).toHaveBeenCalledWith("admin_refund_render_job", { p_admin_id: ADMIN_ID, p_job_id: JOB_ID, p_reason: "GPU crash", p_request_id: "refund:req12345678" });
  });

  it("answers 409 for a job that is not failed or cancelled", async () => {
    h.rpc.mockResolvedValue({ data: null, error: { code: "22023", message: `job ${JOB_ID} is running, only failed or cancelled jobs are refunded` } });
    const res = await refund.POST(post(`/api/admin/renders/${JOB_ID}/refund`, { reason: "GPU crash", request_id: "req12345678" }), ctx(JOB_ID));
    expect(res.status).toBe(409);
  });
});

describe("render retries", () => {
  beforeEach(() => {
    h.session = { id: ADMIN_ID };
    h.tables.render_jobs = failedJob;
  });

  it("resubmits through the pipeline under a key derived from the failed job, and audits once per job", async () => {
    const newRow = { id: "b1b2c3d4-0000-4000-8000-000000000009", cost_credits: 3, status: "queued" };
    h.create.mockResolvedValueOnce({ ok: true, value: { row: newRow, replay: false } }).mockResolvedValueOnce({ ok: true, value: { row: newRow, replay: true } });
    h.rpc.mockResolvedValue({ data: true, error: null });

    const first = await retry.POST(post(`/api/admin/renders/${JOB_ID}/retry`, { reason: "transient OOM" }), ctx(JOB_ID));
    expect(first.status).toBe(201);
    const second = await retry.POST(post(`/api/admin/renders/${JOB_ID}/retry`, {}), ctx(JOB_ID));
    expect(second.status).toBe(200);
    expect(await second.json()).toEqual({ result: { replay: true, job_id: newRow.id, status: "queued" } });

    for (const [input] of h.create.mock.calls) {
      expect(input).toMatchObject({ userId: USER_ID, projectId: failedJob.project_id, uploadId: failedJob.upload_id, idempotencyKey: retryKey(JOB_ID) });
      expect(input.params).toEqual({ prompt: "orbit", tier: "preview" });
    }
    const audits = h.rpc.mock.calls.filter((c) => c[0] === "admin_record_action").map((c) => c[1] as Record<string, unknown>);
    expect(audits).toHaveLength(2);
    expect(new Set(audits.map((a) => a.p_request_id))).toEqual(new Set([`retry:${JOB_ID}`]));
    expect(audits[0]).toMatchObject({ p_admin_id: ADMIN_ID, p_action: "render_retry", p_target_id: JOB_ID, p_reason: "transient OOM" });
  });

  it.each([
    ["a succeeded job", { status: "succeeded" }],
    ["a failure the worker marked final", { retryable: false }],
    ["a job whose model is gone", { upload_id: null }],
  ])("refuses %s", async (_name, patch) => {
    h.tables.render_jobs = { ...failedJob, ...patch };
    const res = await retry.POST(post(`/api/admin/renders/${JOB_ID}/retry`, {}), ctx(JOB_ID));
    expect(res.status).toBe(409);
    expect(h.create).not.toHaveBeenCalled();
    expect(h.rpc).not.toHaveBeenCalled();
  });

  it("writes no audit row when the pipeline refuses", async () => {
    h.create.mockResolvedValue({ ok: false, status: 402, code: "insufficient_credits", message: "You need 3 credits but have 0." });
    const res = await retry.POST(post(`/api/admin/renders/${JOB_ID}/retry`, {}), ctx(JOB_ID));
    expect(res.status).toBe(402);
    expect(h.rpc).not.toHaveBeenCalled();
  });
});

describe("admin routing", () => {
  it("recognises the console and its API, nothing else", () => {
    for (const p of ["/admin", "/admin/users/x", "/api/admin", "/api/admin/overview"]) expect(isAdminPath(p)).toBe(true);
    for (const p of ["/administrator", "/api/adminx", "/projects", "/", "/api/renders"]) expect(isAdminPath(p)).toBe(false);
  });

  it("fails closed when the admin lookup errors or throws", async () => {
    const client = (result: () => Promise<Result>) =>
      ({ from: () => ({ select: () => ({ eq: () => ({ maybeSingle: result }) }) }) }) as never;
    expect(await isAdminUser(client(async () => ({ data: { user_id: ADMIN_ID }, error: null })), ADMIN_ID)).toBe(true);
    expect(await isAdminUser(client(async () => ({ data: null, error: null })), USER_ID)).toBe(false);
    expect(await isAdminUser(client(async () => ({ data: { user_id: ADMIN_ID }, error: { message: "boom" } })), ADMIN_ID)).toBe(false);
    expect(await isAdminUser(client(async () => Promise.reject(new Error("network"))), ADMIN_ID)).toBe(false);
  });

  it("highlights the right section", () => {
    expect(sectionFor("/admin", "/admin")).toBe("overview");
    expect(sectionFor("/admin/renders/abc", "/admin")).toBe("renders");
    expect(sectionFor("/dev/admin/users", "/dev/admin")).toBe("users");
    expect(ADMIN_SECTIONS.map((s) => s.id)).toEqual(["overview", "renders", "users", "billing", "audit"]);
  });
});

describe("billing webhook error log", () => {
  const SECRET = "pdl_ntfset_admin_lane_test_secret";
  const NOW = Date.UTC(2026, 8, 29, 12, 0, 0);
  const billingConfig = { environment: "sandbox" as const, apiKey: null, webhookSecret: SECRET, prices: {} };
  const signed = async (body: string) =>
    new Request(`${ORIGIN}/api/billing/webhook`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Paddle-Signature": await signPaddlePayload(body, SECRET, Math.floor(NOW / 1000)) },
      body,
    });
  const event = JSON.stringify({ event_id: "evt_01admin", event_type: "customer.created", occurred_at: "2026-09-29T11:59:00Z", data: {} });

  it("records an apply failure and still answers 500 for Paddle to retry", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const recordError = vi.fn(async () => ({}));
    const apply = vi.fn(async () => ({ data: null, error: { code: "P0001", message: "no owner" } }));
    const res = await handleWebhook(await signed(event), billingConfig, apply, NOW, recordError);
    expect(res.status).toBe(500);
    expect(recordError).toHaveBeenCalledWith({ stage: "apply", eventId: "evt_01admin", eventType: "customer.created", code: "P0001", message: "no owner" });
  });

  it("records an unmappable signed body, but never an unsigned one", async () => {
    const recordError = vi.fn(async () => ({}));
    const apply = vi.fn();
    expect((await handleWebhook(await signed("[]"), billingConfig, apply, NOW, recordError)).status).toBe(400);
    expect(recordError).toHaveBeenCalledWith(expect.objectContaining({ stage: "parse" }));
    recordError.mockClear();
    const unsigned = new Request(`${ORIGIN}/api/billing/webhook`, { method: "POST", body: event });
    expect((await handleWebhook(unsigned, billingConfig, apply, NOW, recordError)).status).toBe(401);
    expect(recordError).not.toHaveBeenCalled();
  });

  it("never lets a failing log change the answer", async () => {
    const recordError = vi.fn(async () => Promise.reject(new Error("log table missing")));
    const apply = vi.fn(async () => ({ data: { outcome: "ignored" }, error: null }));
    const ok = await handleWebhook(await signed(event), billingConfig, apply, NOW, recordError);
    expect(ok.status).toBe(200);
    expect((await handleWebhook(await signed("[]"), billingConfig, apply, NOW, recordError)).status).toBe(400);
  });
});
