import { describe, expect, it, vi } from "vitest";
import type { RenderJob } from "@/lib/schema";
import { HttpRenderService, POLL, nextDelay } from "./render";

const job = (patch: Partial<RenderJob> = {}): RenderJob => ({
  id: "j1", projectId: "p1", versionId: null, kind: "preview", target: "cloud", status: "QUEUED",
  frame: 0, totalFrames: 1, error: null, resultUrl: null, ...patch,
});

/** A manual clock: `flush()` runs every due timer, in order. */
function manualTimer() {
  const queue: { fn: () => void; ms: number; id: number }[] = [];
  let id = 0;
  return {
    delays: [] as number[],
    set(fn: () => void, ms: number) {
      this.delays.push(ms);
      queue.push({ fn, ms, id: ++id });
      return id;
    },
    clear(h: unknown) {
      const i = queue.findIndex((q) => q.id === h);
      if (i >= 0) queue.splice(i, 1);
    },
    async step() {
      const next = queue.shift();
      next?.fn();
      // Let the awaited fetch + json settle.
      for (let i = 0; i < 10; i++) await Promise.resolve();
    },
    get pending() {
      return queue.length;
    },
  };
}

describe("HttpRenderService", () => {
  it("POSTs the contract body with snake_case keys", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ job: job() }, { status: 201 }));
    const svc = new HttpRenderService(fetchImpl as unknown as typeof fetch);
    const r = await svc.request({ projectId: "p1", uploadId: "a1", versionId: "v1", params: { prompt: "x", tier: "preview" }, idempotencyKey: "k-12345678" });
    expect(r.ok && r.value.id).toBe("j1");
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/renders");
    expect(JSON.parse(String(init.body))).toEqual({ project_id: "p1", upload_id: "a1", version_id: "v1", params: { prompt: "x", tier: "preview" }, idempotency_key: "k-12345678" });
  });

  it("maps the server's not_connected (no RunPod env) to the studio's recovery state, and keeps other errors", async () => {
    const nc = new HttpRenderService((async () => Response.json({ error: { code: "not_connected", message: "Rendering is currently unavailable." } }, { status: 503 })) as unknown as typeof fetch);
    const r = await nc.request({ projectId: "p", uploadId: "a", versionId: null, params: {}, idempotencyKey: "k-12345678" });
    expect(!r.ok && r.error.code).toBe("not_connected");
    const broke = new HttpRenderService((async () => Response.json({ error: { code: "insufficient_credits", message: "You need 60 credits but have 3." } }, { status: 402 })) as unknown as typeof fetch);
    const b = await broke.request({ projectId: "p", uploadId: "a", versionId: null, params: {}, idempotencyKey: "k-12345678" });
    expect(!b.ok && b.error).toEqual({ code: "insufficient_credits", message: "You need 60 credits but have 3." });
  });

  it("polls until the job is terminal, slower while queued, backing off on errors", async () => {
    const answers: Response[] = [
      Response.json({ job: job({ status: "QUEUED" }) }),
      new Response("", { status: 502 }),
      Response.json({ job: job({ status: "RENDERING", frame: 10, totalFrames: 300 }) }),
      Response.json({ job: job({ status: "COMPLETE", resultUrl: "https://v" }) }),
    ];
    const timer = manualTimer();
    const svc = new HttpRenderService((async () => answers.shift()!) as unknown as typeof fetch, timer);
    const seen: string[] = [];
    svc.subscribe("j1", (j) => seen.push(j.status));
    for (let i = 0; i < 6 && timer.pending; i++) await timer.step();
    expect(seen).toEqual(["QUEUED", "RENDERING", "COMPLETE"]);
    expect(timer.delays).toEqual([0, POLL.queuedMs, POLL.activeMs * 2, POLL.activeMs]);
    expect(timer.pending).toBe(0);
  });

  it("stops on unsubscribe and when the job is gone", async () => {
    const timer = manualTimer();
    const fetchImpl = vi.fn(async () => Response.json({ error: { code: "not_found", message: "Render not found." } }, { status: 404 }));
    const svc = new HttpRenderService(fetchImpl as unknown as typeof fetch, timer);
    const onUpdate = vi.fn();
    svc.subscribe("j1", onUpdate);
    await timer.step();
    expect(timer.pending).toBe(0);
    expect(onUpdate).not.toHaveBeenCalled();

    const stop = svc.subscribe("j2", onUpdate);
    stop();
    expect(timer.pending).toBe(0);
  });

  it("caps the backoff", () => {
    expect(nextDelay(null, 10)).toBe(POLL.maxMs);
    expect(nextDelay(job({ status: "RENDERING" }), 0)).toBe(POLL.activeMs);
  });
});
