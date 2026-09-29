import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyPatch } from "@/lib/scene/applyPatch";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { resolveVersionAction, VERSION_ACTION_COST, VERSION_HOURLY_CAP } from "@/lib/scene/versionAction";
import type { VersionRow } from "@/lib/services/supabase/rows";
import { saveSceneVersion, type SaveVersionArgs, type SaveVersionInput, type SavedVersion, type StoreError, type VersionStore } from "./saveVersion";

const USER = "11111111-1111-4111-8111-111111111111";
const PROJECT = "aaaaaaaa-0000-4000-8000-000000000001";
const OTHER_PROJECT = "bbbbbbbb-0000-4000-8000-000000000001";

/** In-memory save_scene_version: the SQL's rules (first = generate, price lookup, balance, cap, idempotency). */
class FakeStore implements VersionStore {
  versions: (VersionRow & { user_id: string; key: string })[] = [];
  balance = 50;
  recent = 0;
  saves: SaveVersionArgs[] = [];
  seq = 0;

  async getParentPlan(userId: string, projectId: string, parentId: string) {
    const v = this.versions.find((x) => x.id === parentId && x.project_id === projectId && x.user_id === userId);
    return v ? { plan: v.plan } : null;
  }

  async save(a: SaveVersionArgs): Promise<{ data: SavedVersion } | { error: StoreError }> {
    this.saves.push(a);
    if (a.projectId !== PROJECT) return { error: { code: "P0002", message: "project not found" } };
    const prior = this.versions.find((v) => v.user_id === a.userId && v.key === a.idempotencyKey);
    if (prior) {
      if (JSON.stringify(prior.plan) !== JSON.stringify(a.plan)) return { error: { code: "23505", message: "idempotency key reused" } };
      return { data: { version: prior, charged: 0, balance: this.balance, replay: true } };
    }
    const index = this.versions.filter((v) => v.project_id === a.projectId).length;
    const cost = VERSION_ACTION_COST[resolveVersionAction(a.action, index)];
    if (this.recent >= VERSION_HOURLY_CAP) return { error: { code: "P0001", message: `rate_limited: max ${VERSION_HOURLY_CAP} per hour` } };
    if (this.balance < 0 || this.balance < cost) return { error: { code: "P0001", message: `insufficient_credits: need ${cost}, have ${this.balance}` } };
    const row = {
      id: `v${++this.seq}`, project_id: a.projectId, index, prompt: a.prompt, parent_id: a.parentId, plan: a.plan,
      created_at: "2026-09-29T00:00:00Z", user_id: a.userId, key: a.idempotencyKey,
    };
    this.versions.push(row);
    this.balance -= cost;
    this.recent += 1;
    return { data: { version: row, charged: cost, balance: this.balance, replay: false } };
  }
}

const plan = defaultPlan("car");
let seq = 0;
const body = (over: Partial<SaveVersionInput> = {}): SaveVersionInput => ({
  prompt: "night", parentId: null, plan, action: "generate", idempotencyKey: `key-${String(++seq).padStart(8, "0")}`, ...over,
});
const json = async (res: Response) => ({ status: res.status, body: await res.json() });

describe("saveSceneVersion", () => {
  let store: FakeStore;
  beforeEach(() => { store = new FakeStore(); });

  it("charges a generation for the first version whatever was declared", async () => {
    const r = await json(await saveSceneVersion(store, USER, PROJECT, body({ action: "adjust" })));
    expect(r.status).toBe(201);
    expect(r.body).toMatchObject({ charged: 5, balance: 45, replay: false });
    expect(store.saves[0]).toMatchObject({ userId: USER, projectId: PROJECT, action: "adjust" });
  });

  it("charges 2 for an edit and 0 for a real slider adjustment", async () => {
    await saveSceneVersion(store, USER, PROJECT, body());
    const parentId = store.versions[0].id;
    const edit = await json(await saveSceneVersion(store, USER, PROJECT,
      body({ action: "edit", parentId, plan: applyPatch(plan, { operation: "set_scene", environment: "urban_night" }) })));
    expect(edit.body.charged).toBe(2);
    const adj = await json(await saveSceneVersion(store, USER, PROJECT,
      body({ action: "adjust", parentId, plan: applyPatch(plan, { operation: "set_scene", fogDensity: 0.05 }) })));
    expect(adj.status).toBe(201);
    expect(adj.body.charged).toBe(0);
    expect(store.balance).toBe(43);
  });

  it("refuses a free adjustment that is really an edit", async () => {
    await saveSceneVersion(store, USER, PROJECT, body());
    const r = await json(await saveSceneVersion(store, USER, PROJECT,
      body({ action: "adjust", parentId: store.versions[0].id, plan: applyPatch(plan, { operation: "set_scene", environment: "urban_night" }) })));
    expect(r.status).toBe(400);
    expect(r.body.error.code).toBe("not_an_adjustment");
    expect(store.saves).toHaveLength(1);
  });

  it("404s an adjustment of a version that is not in this project", async () => {
    const r = await saveSceneVersion(store, USER, PROJECT, body({ action: "adjust", parentId: "cccccccc-0000-4000-8000-000000000001" }));
    expect(r.status).toBe(404);
  });

  it("validates the plan with the scene schema before touching the database", async () => {
    const bad = await json(await saveSceneVersion(store, USER, PROJECT, body({ plan: { ...plan, camera: { ...plan.camera, lensMm: 5 } } })));
    expect(bad.status).toBe(400);
    expect(bad.body.error.code).toBe("invalid_plan");
    expect((await saveSceneVersion(store, USER, PROJECT, body({ plan: "nope" }))).status).toBe(400);
    expect(store.saves).toHaveLength(0);
  });

  it("answers 402 with a clear message when the balance is short, and when it is negative", async () => {
    store.balance = 1;
    const short = await json(await saveSceneVersion(store, USER, PROJECT, body()));
    expect(short.status).toBe(402);
    expect(short.body.error).toEqual({ code: "insufficient_credits", message: "You need 5 credits but have 1." });
    store.balance = -5;
    const neg = await json(await saveSceneVersion(store, USER, PROJECT, body()));
    expect(neg.status).toBe(402);
    expect(neg.body.error.message).toMatch(/balance is -5 credits/);
    expect(store.versions).toHaveLength(0);
  });

  it("returns the saved version on a replay, charged once", async () => {
    const b = body();
    await saveSceneVersion(store, USER, PROJECT, b);
    const again = await json(await saveSceneVersion(store, USER, PROJECT, b));
    expect(again.status).toBe(200);
    expect(again.body).toMatchObject({ charged: 0, replay: true, balance: 45 });
    expect(store.versions).toHaveLength(1);
    const reused = await saveSceneVersion(store, USER, PROJECT, { ...b, plan: applyPatch(plan, { operation: "set_scene", fogDensity: 0.02 }) });
    expect(reused.status).toBe(409);
  });

  it("rate-limits at the hourly cap (429)", async () => {
    store.recent = VERSION_HOURLY_CAP;
    const r = await json(await saveSceneVersion(store, USER, PROJECT, body()));
    expect(r.status).toBe(429);
    expect(r.body.error.code).toBe("rate_limited");
  });

  it("404s a malformed or foreign project id", async () => {
    expect((await saveSceneVersion(store, USER, "not-a-uuid", body())).status).toBe(404);
    expect((await saveSceneVersion(store, USER, OTHER_PROJECT, body())).status).toBe(404);
  });
});

// The route: auth, same-origin, body shape, then one call on the service-role store.
const rpc = vi.fn();
const maybeSingle = vi.fn();
vi.mock("@/lib/supabase/server", async (orig) => {
  const actual = await orig<typeof import("@/lib/supabase/server")>();
  return {
    ...actual,
    requireUser: vi.fn(async () => ({ config: {}, user: { id: USER }, userClient: {} })),
    createServiceSupabase: vi.fn(() => {
      const q: Record<string, unknown> = {};
      q.select = () => q;
      q.eq = () => q;
      q.maybeSingle = maybeSingle;
      return { rpc, from: () => q };
    }),
  };
});

describe("POST /api/projects/:id/versions", () => {
  const url = `https://valora3d.com/api/projects/${PROJECT}/versions`;
  const req = (payload: unknown, origin = "https://valora3d.com") =>
    new Request(url, { method: "POST", headers: { origin, "content-type": "application/json" }, body: JSON.stringify(payload) });
  const ctx = { params: Promise.resolve({ id: PROJECT }) };
  const saved = { data: { version: { id: "v1" }, charged: 5, balance: 45, replay: false }, error: null };
  beforeEach(() => { rpc.mockReset(); maybeSingle.mockReset(); });

  it("calls save_scene_version once with the signed-in user and no amount", async () => {
    const { POST } = await import("@/app/api/projects/[id]/versions/route");
    rpc.mockResolvedValue(saved);
    const res = await POST(req(body({ idempotencyKey: "key-abcdefgh" })), ctx);
    expect(res.status).toBe(201);
    expect(rpc).toHaveBeenCalledTimes(1);
    const [fn, args] = rpc.mock.calls[0];
    expect(fn).toBe("save_scene_version");
    expect(args).toMatchObject({ p_user_id: USER, p_project_id: PROJECT, p_action: "generate", p_idempotency_key: "key-abcdefgh" });
  });

  it("ignores any amount the browser sends and refuses bad bodies and cross-origin calls", async () => {
    const { POST } = await import("@/app/api/projects/[id]/versions/route");
    rpc.mockResolvedValue(saved);
    await POST(req({ ...body(), amount: 0, cost: 0 }), ctx);
    expect(Object.keys(rpc.mock.calls[0][1]).sort()).toEqual(
      ["p_action", "p_idempotency_key", "p_parent_id", "p_plan", "p_project_id", "p_prompt", "p_user_id"]);
    expect((await POST(req({ ...body(), action: "free" }), ctx)).status).toBe(400);
    expect((await POST(req({ ...body(), idempotencyKey: "short" }), ctx)).status).toBe(400);
    expect((await POST(req(body(), "https://evil.example"), ctx)).status).toBe(403);
    expect(rpc).toHaveBeenCalledTimes(1);
  });

  it("checks an adjustment against the stored parent", async () => {
    const { POST } = await import("@/app/api/projects/[id]/versions/route");
    maybeSingle.mockResolvedValue({ data: { plan }, error: null });
    const parentId = "cccccccc-0000-4000-8000-000000000001";
    const res = await POST(req(body({ action: "adjust", parentId, plan: applyPatch(plan, { operation: "set_scene", ground: "wet_asphalt" }) })), ctx);
    expect(res.status).toBe(400);
    expect(rpc).not.toHaveBeenCalled();
  });

  it("maps the SQL refusals: 402 insufficient credits, 429 rate limit", async () => {
    const { POST } = await import("@/app/api/projects/[id]/versions/route");
    rpc.mockResolvedValueOnce({ data: null, error: { code: "P0001", message: "insufficient_credits: need 1, have 0" } });
    expect((await POST(req(body()), ctx)).status).toBe(402);
    rpc.mockResolvedValueOnce({ data: null, error: { code: "P0001", message: "rate_limited: max 120 per hour" } });
    expect((await POST(req(body()), ctx)).status).toBe(429);
  });
});
