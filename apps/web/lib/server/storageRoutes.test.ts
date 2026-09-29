import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Route-level regressions for the storage findings: project deletion only through the service role with R2
 * cleanup queued (H2), the upload cap through create_upload (H2/L8), account deletion queuing render outputs and
 * finishing even when R2 is down (H1), and the webhook's body cap (L6).
 */

const USER = "11111111-1111-4111-8111-111111111111";
const PROJECT = "aaaaaaaa-0000-4000-8000-000000000001";

type Call = { table: string; op: string; args: unknown[] };
const calls: Call[] = [];
const rpc = vi.fn();
let liveCount = 0;
let liveJobs: { runpod_id: string }[] = [];
let ownsProject = true;
let r2Config: Record<string, string> | undefined;
let runpodConfig: Record<string, string> | undefined;

function query(table: string) {
  const q: Record<string, unknown> = {};
  let op = "select";
  const rec = (name: string) => (...args: unknown[]) => {
    calls.push({ table, op: name, args });
    if (name === "delete") op = "delete";
    return q;
  };
  for (const m of ["select", "eq", "in", "not", "neq", "delete", "insert", "order", "limit"]) q[m] = rec(m);
  q.maybeSingle = async () => ({ data: table.endsWith("projects") && ownsProject ? { id: PROJECT } : null, error: null });
  q.then = (resolve: (v: unknown) => void) => {
    if (op === "delete") return resolve({ error: null });
    if (table === "render_jobs") return resolve({ data: liveJobs, count: liveCount, error: null });
    return resolve({ data: [], error: null });
  };
  return q;
}

const userClient = { from: (t: string) => query(`user:${t}`), auth: { signOut: vi.fn(async () => ({})) } };
const deleteUser = vi.fn(async () => ({ error: null }));

vi.mock("@/lib/supabase/server", async (orig) => {
  const actual = await orig<typeof import("@/lib/supabase/server")>();
  return {
    ...actual,
    requireUser: vi.fn(async () => ({ config: { r2: r2Config, runpod: runpodConfig }, user: { id: USER }, userClient })),
    createServiceSupabase: vi.fn(() => ({
      rpc: (...args: unknown[]) => {
        const r = rpc(...args);
        return Object.assign(Promise.resolve(r), { single: async () => r });
      },
      from: (t: string) => query(t),
      auth: { admin: { deleteUser } },
    })),
  };
});

const bucketDeletes: string[] = [];
let r2Down = false;
vi.mock("@/lib/server/r2", () => ({
  R2Storage: class {
    async delete(key: string) {
      if (r2Down) throw new Error("R2 DELETE failed: 503");
      bucketDeletes.push(key);
    }
    async deletePrefixBounded(prefix: string) {
      if (r2Down) throw new Error("R2 LIST failed: 503");
      bucketDeletes.push(prefix);
      return { removed: 1, complete: true, ops: 2 };
    }
    async presignPut() {
      return { url: "https://r2/put", headers: {} };
    }
  },
}));

const cancelled: string[] = [];
vi.mock("@/lib/server/runpod", () => ({
  RunpodClient: class {
    async cancel(id: string) {
      cancelled.push(id);
      return null;
    }
  },
}));

vi.mock("@/lib/env", async (orig) => ({ ...(await orig<typeof import("@/lib/env")>()), billingConfig: () => null }));

beforeEach(() => {
  calls.length = 0;
  bucketDeletes.length = 0;
  cancelled.length = 0;
  rpc.mockReset();
  deleteUser.mockClear();
  liveCount = 0;
  liveJobs = [];
  ownsProject = true;
  r2Config = { accountId: "a", bucket: "b", accessKeyId: "k", secretAccessKey: "s" };
  runpodConfig = undefined;
  r2Down = false;
});

const same = { origin: "https://valora3d.com" };

describe("DELETE /api/projects/:id (H2)", () => {
  const ctx = { params: Promise.resolve({ id: PROJECT }) };
  const req = () => new Request(`https://valora3d.com/api/projects/${PROJECT}`, { method: "DELETE", headers: same });

  it("deletes through the service role (scoped to the owner), never the user's client, then drains the queue", async () => {
    const { DELETE } = await import("@/app/api/projects/[id]/route");
    rpc.mockImplementation((fn: string) =>
      fn === "claim_storage_purges"
        ? { data: [{ id: 1, user_id: USER, target: `r/${USER}/${PROJECT}/` }], error: null }
        : { data: 1, error: null },
    );
    const res = await DELETE(req(), ctx);
    expect(res.status).toBe(204);
    expect(calls.some((c) => c.table.startsWith("user:") && c.op === "delete")).toBe(false);
    const del = calls.findIndex((c) => c.table === "projects" && c.op === "delete");
    expect(del).toBeGreaterThanOrEqual(0);
    expect(calls.slice(del).filter((c) => c.op === "eq").map((c) => c.args)).toEqual(
      expect.arrayContaining([["id", PROJECT], ["user_id", USER]]),
    );
    expect(rpc).toHaveBeenCalledWith("claim_storage_purges", { p_limit: 50, p_user_id: USER });
    expect(bucketDeletes).toEqual([`r/${USER}/${PROJECT}/`]);
    expect(rpc).toHaveBeenCalledWith("complete_storage_purges", { p_ids: [1] });
  });

  it("refuses while a render is live (its worker could still write outputs)", async () => {
    const { DELETE } = await import("@/app/api/projects/[id]/route");
    liveCount = 1;
    const res = await DELETE(req(), ctx);
    expect(res.status).toBe(409);
    expect(calls.some((c) => c.op === "delete")).toBe(false);
  });

  it("still answers 204 when R2 is down: the queue keeps the files for the sweep", async () => {
    const { DELETE } = await import("@/app/api/projects/[id]/route");
    r2Down = true;
    rpc.mockImplementation((fn: string) =>
      fn === "claim_storage_purges" ? { data: [{ id: 7, user_id: USER, target: `u/${USER}/` }], error: null } : { data: 1, error: null },
    );
    expect((await DELETE(req(), ctx)).status).toBe(204);
    expect(rpc).toHaveBeenCalledWith("release_storage_purges", { p_ids: [7], p_error: "R2 delete failed" });
  });

  it("answers 404 for a project the caller cannot see", async () => {
    const { DELETE } = await import("@/app/api/projects/[id]/route");
    ownsProject = false;
    expect((await DELETE(req(), ctx)).status).toBe(404);
  });
});

describe("POST /api/uploads (H2, L8)", () => {
  const req = () =>
    new Request("https://valora3d.com/api/uploads", {
      method: "POST",
      headers: { ...same, "content-type": "application/json" },
      body: JSON.stringify({ kind: "upload", projectId: PROJECT, fileName: "car.glb", sizeBytes: 1024 }),
    });

  it("creates the row through create_upload (cap and ownership under the lock) and signs the PUT", async () => {
    const { POST } = await import("@/app/api/uploads/route");
    rpc.mockReturnValue({ data: { id: "u1" }, error: null });
    const res = await POST(req());
    expect(res.status).toBe(201);
    const [fn, args] = rpc.mock.calls[0];
    expect(fn).toBe("create_upload");
    expect(args).toMatchObject({ p_user_id: USER, p_project_id: PROJECT, p_file_name: "car.glb", p_size_bytes: 1024 });
    expect(String(args.p_r2_key)).toMatch(new RegExp(`^u/${USER}/[0-9a-f-]{36}\\.glb$`));
    expect(calls.some((c) => c.table === "uploads")).toBe(false); // no row count, no direct insert
  });

  it("answers 429 when create_upload reports the cap", async () => {
    const { POST } = await import("@/app/api/uploads/route");
    rpc.mockReturnValue({ data: null, error: { code: "P0001", message: "rate_limited: uploads" } });
    expect((await POST(req())).status).toBe(429);
  });
});

describe("POST /api/account/delete (H1)", () => {
  const req = () => new Request("https://valora3d.com/api/account/delete", { method: "POST", headers: same });

  it("cancels live renders, queues models AND render outputs (now and late), and deletes the user", async () => {
    const { POST } = await import("@/app/api/account/delete/route");
    runpodConfig = { apiKey: "k", endpointId: "e" };
    liveJobs = [{ runpod_id: "rp-live" }];
    rpc.mockImplementation((fn: string) => (fn === "claim_storage_purges" ? { data: [], error: null } : { data: null, error: null }));
    const res = await POST(req());
    expect(res.status).toBe(204);
    expect(cancelled).toEqual(["rp-live"]);
    const targets = rpc.mock.calls.filter(([fn]) => fn === "enqueue_storage_purge").map(([, a]) => a.p_target);
    expect(targets).toEqual([`u/${USER}/`, `r/${USER}/`, `u/${USER}/`, `r/${USER}/`]);
    expect(deleteUser).toHaveBeenCalledWith(USER);
  });

  it("completes the deletion when R2 is down: the queued prefixes are drained later by the sweep", async () => {
    const { POST } = await import("@/app/api/account/delete/route");
    r2Down = true;
    rpc.mockImplementation((fn: string) =>
      fn === "claim_storage_purges" ? { data: [{ id: 1, user_id: USER, target: `r/${USER}/` }], error: null } : { data: null, error: null },
    );
    expect((await POST(req())).status).toBe(204);
    expect(deleteUser).toHaveBeenCalledWith(USER);
    expect(rpc).toHaveBeenCalledWith("release_storage_purges", { p_ids: [1], p_error: "R2 delete failed" });
  });

  it("keeps the account when the files cannot even be queued", async () => {
    const { POST } = await import("@/app/api/account/delete/route");
    rpc.mockReturnValue({ data: null, error: { message: "db down" } });
    expect((await POST(req())).status).toBe(502);
    expect(deleteUser).not.toHaveBeenCalled();
  });
});

describe("POST /api/runpod/webhook (L6)", () => {
  it("refuses a declared or streamed body over 1 MB before touching the pipeline", async () => {
    vi.resetModules();
    const webhook = vi.fn(async () => ({ status: 200, note: "applied" }));
    vi.doMock("@/lib/env", async (orig) => ({ ...(await orig<typeof import("@/lib/env")>()), serverConfig: () => ({ runpod: {} }) }));
    vi.doMock("@/lib/server/renderContext", () => ({ createRenderPipeline: () => ({ webhook }) }));
    const { POST } = await import("@/app/api/runpod/webhook/route");
    const url = "https://valora3d.com/api/runpod/webhook?job=x&t=y";
    const declared = new Request(url, { method: "POST", headers: { "content-length": "2000000" }, body: "{}" });
    expect((await POST(declared)).status).toBe(413);
    const big = new Request(url, { method: "POST", body: "x".repeat(1_000_001) });
    expect((await POST(big)).status).toBe(413);
    expect(webhook).not.toHaveBeenCalled();
    const ok = new Request(url, { method: "POST", body: JSON.stringify({ id: "rp-1", status: "COMPLETED" }) });
    expect((await POST(ok)).status).toBe(200);
    expect(webhook).toHaveBeenCalledWith("x", "y", { id: "rp-1", status: "COMPLETED" }, "https://valora3d.com");
  });
});
