import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  SITE_ERRORS,
  WORKER_ERRORS,
  interpretStatus,
  outputKey,
  presignLifetimes,
  rowStatus,
  stageToStatus,
  workerCodeFromError,
} from "./contract";
import { renderCost } from "./cost";
import { expiresAtMs, rowToRenderJob, type RenderJobRow } from "./jobRow";
import { DURATION_RANGE, MAX_PROMPT, SEED_LIMIT, RenderParamsSchema, WorkerParamsSchema, normalizeParams, parseRenderParams } from "./params";
import { limitsFromRow, renderPlanLimits } from "./planLimits";
import { CREDIT_COSTS, PLAN_LIMITS } from "@/lib/pricing";
import { WORLDS, WORLD_IDS, worldLabel } from "./worlds";

describe("render params (worker contract)", () => {
  it("accepts the minimal request and defaults the tier to preview", () => {
    const r = parseRenderParams({});
    expect(r).toEqual({ ok: true, value: { prompt: "", tier: "preview" } });
  });

  it("accepts every field the worker takes and normalizes it", () => {
    const r = parseRenderParams({
      prompt: "  slow   orbit\n in the rain ", world: "rain_courtyard", aspect: "9:16", tier: "final",
      seed: 0, duration: 12, paint: "#1A2B3C", finish: "metallic",
    });
    expect(r).toEqual({
      ok: true,
      value: { prompt: "slow orbit in the rain", tier: "final", world: "rain_courtyard", aspect: "9:16", seed: 0, duration: 12, paint: "#1a2b3c", finish: "metallic" },
    });
  });

  it("defaults finish to gloss when only paint is given (the worker's default)", () => {
    const r = parseRenderParams({ paint: "#ffffff" });
    expect(r.ok && r.value.finish).toBe("gloss");
  });

  it.each([
    ["an unknown key (worker: INVALID_INPUT)", { markers: [] }],
    ["an unknown world", { world: "moon_base" }],
    ["a world id with bad characters", { world: "Rain Courtyard" }],
    ["another aspect", { aspect: "1:1" }],
    ["another tier", { tier: "keyframes" }],
    ["a fractional seed", { seed: 1.5 }],
    ["a negative seed", { seed: -1 }],
    ["a seed at the limit", { seed: SEED_LIMIT }],
    ["a too-short clip", { duration: DURATION_RANGE[0] - 0.5 }],
    ["a too-long clip", { duration: DURATION_RANGE[1] + 1 }],
    // M1: renders are priced flat for 8-12 s clips, so only the offered lengths are accepted.
    ["the worker's minimum (not offered)", { duration: DURATION_RANGE[0] }],
    ["the worker's maximum (not offered)", { duration: DURATION_RANGE[1] }],
    ["a length between the offered ones", { duration: 9 }],
    ["a 30 s pin in the prompt (the director lets it beat duration)", { prompt: "a slow 30 second orbit", duration: 10 }],
    ["a 3 s pin in the prompt", { prompt: "3s teaser" }],
    ["a 60 fps pin in the prompt", { prompt: "orbit at 60fps" }],
    ["a short hex", { paint: "#fff" }],
    ["a named colour", { paint: "red" }],
    ["an unknown finish", { paint: "#000000", finish: "chrome" }],
    ["a finish without paint", { finish: "matte" }],
    ["a prompt over the limit", { prompt: "x".repeat(MAX_PROMPT + 1) }],
    ["a NUL in the prompt", { prompt: "a\u0000b" }],
    ["a non-object", "rain"],
  ])("refuses %s", (_label, input) => {
    expect(parseRenderParams(input).ok).toBe(false);
  });

  it.each([8, 10, 12])("accepts the offered %s s length", (duration) => {
    expect(parseRenderParams({ duration }).ok).toBe(true);
  });

  it("accepts prompt numbers that are not a length outside 8-12 s", () => {
    for (const prompt of ["a 10s orbit", "12-second reveal", "3 cars at 24 fps", "2.5x zoom on 911 GT3"]) {
      expect(parseRenderParams({ prompt }).ok, prompt).toBe(true);
    }
  });

  it("keeps a prompt of exactly the limit and a seed just under it", () => {
    expect(parseRenderParams({ prompt: "x".repeat(MAX_PROMPT), seed: SEED_LIMIT - 1 }).ok).toBe(true);
  });

  it("normalizes to a stable shape, so a retried request matches the stored params", () => {
    const a = normalizeParams({ prompt: "a", tier: "preview", seed: 1, world: "studio_cyc" });
    const b = normalizeParams({ world: "studio_cyc", seed: 1, tier: "preview", prompt: "a" });
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });
});

describe("worlds", () => {
  it("lists the graded worlds from engine/site_job.py (snapshot) with unique engine-shaped ids", () => {
    expect(WORLD_IDS).toEqual(["studio_cyc", "rain_courtyard", "night_street", "golden_field"]);
    for (const w of WORLDS) expect(w.id).toMatch(/^[a-z0-9_]{1,64}$/);
    expect(worldLabel(null)).toBe("Auto");
    expect(worldLabel("night_street")).toBe("Night street");
  });
});

describe("pricing and plan gate", () => {
  it("charges each tier from lib/pricing", () => {
    expect(renderCost("preview")).toBe(CREDIT_COSTS.preview_render);
    expect(renderCost("final")).toBe(CREDIT_COSTS.final_render);
  });
  it("displays the billing lane's PLAN_LIMITS: Free previews only, watermarked; unknown => Free", () => {
    expect(renderPlanLimits("free")).toBe(PLAN_LIMITS.free);
    expect(renderPlanLimits("free").tiers).toEqual(["preview"]);
    expect(renderPlanLimits("free").watermark).toBe(true);
    expect(renderPlanLimits(null).tiers).toEqual(["preview"]);
    expect(renderPlanLimits("creator").tiers).toContain("final");
    expect(renderPlanLimits("pro")).toMatchObject({ watermark: false, maxActiveJobs: 3, retentionDays: 90 });
  });
  it("parses a user_plan_limits row, failing closed to Free on anything malformed", () => {
    const pro = { plan: "pro", max_resolution: "1080p", tiers: ["preview", "final"], watermark: false, retention_days: 90, max_active_jobs: 3, plan_rank: 2 };
    expect(limitsFromRow(pro)).toEqual({ plan: "pro", limits: PLAN_LIMITS.pro });
    expect(limitsFromRow(null)).toEqual({ plan: "free", limits: PLAN_LIMITS.free });
    expect(limitsFromRow({ ...pro, plan: "enterprise" }).plan).toBe("free");
    expect(limitsFromRow({ ...pro, tiers: ["4k"] }).plan).toBe("free");
    expect(limitsFromRow({ ...pro, watermark: null as unknown as boolean }).plan).toBe("free");
    expect(limitsFromRow({ ...pro, max_active_jobs: 0 }).plan).toBe("free");
    expect(limitsFromRow({ ...pro, tiers: ["preview", "final", "4k"] }).limits.tiers).toEqual(["preview", "final"]);
  });
});

describe("watermark (server-injected, never from the browser)", () => {
  it("refuses a browser request that carries watermark, in either value", () => {
    expect(parseRenderParams({ prompt: "x", watermark: false }).ok).toBe(false);
    expect(parseRenderParams({ prompt: "x", watermark: true }).ok).toBe(false);
    expect(RenderParamsSchema.safeParse({ watermark: true }).success).toBe(false);
  });
  it("lets the worker params carry it (the worker's strict parse_params knows the key)", () => {
    expect(WorkerParamsSchema.safeParse({ prompt: "x", tier: "preview", watermark: true }).success).toBe(true);
    expect(WorkerParamsSchema.safeParse({ prompt: "x", tier: "preview", watermark: "yes" }).success).toBe(false);
    expect(WorkerParamsSchema.safeParse({ prompt: "x", tier: "preview", junk: 1 }).success).toBe(false);
  });
  it("matches the worker contract's known keys", () => {
    const contract = join(import.meta.dirname, "../../../../../Rendering-worker/worker/contract.py");
    let py: string;
    try {
      py = readFileSync(contract, "utf8");
    } catch {
      return; // the worker repo is a sibling checkout; not every environment has it
    }
    const known = py.match(/known = \{([^}]*)\}/)?.[1] ?? "";
    for (const key of Object.keys(WorkerParamsSchema.shape)) expect(known).toContain(`"${key}"`);
  });
});

describe("RunPod status -> job (contract mapping)", () => {
  const JOB = "job-1";

  it("reads the queue and live progress", () => {
    expect(interpretStatus({ status: "IN_QUEUE" }, JOB)).toEqual({ kind: "queued" });
    expect(interpretStatus({ status: "IN_PROGRESS", output: { job_id: JOB, stage: "render", status: "RENDERING", frame: 42, total_frames: 300 } }, JOB)).toEqual({
      kind: "running", stage: "render", frame: 42, totalFrames: 300,
    });
    // No progress payload yet, or one with a stage we do not know.
    expect(interpretStatus({ status: "IN_PROGRESS" }, JOB)).toEqual({ kind: "running", stage: null, frame: null, totalFrames: null });
    expect(interpretStatus({ status: "IN_PROGRESS", output: { stage: "warp" } }, JOB)).toMatchObject({ stage: null });
  });

  it("reads a success, keeping only the known outputs", () => {
    const it_ = interpretStatus({
      status: "COMPLETED",
      output: {
        status: "succeeded", job_id: JOB, outputs: { video: { bytes: 10, content_type: "video/mp4" }, evil: { bytes: 1 } },
        frames: 300, fps: 30, render_seconds: 512.3, gpu_seconds: 571.9, warnings: ["markers ignored", 7], pin: { blender: "5.0.1" },
      },
    }, JOB);
    expect(it_.kind).toBe("succeeded");
    if (it_.kind !== "succeeded") return;
    expect(Object.keys(it_.result.outputs)).toEqual(["video"]);
    expect(it_.result).toMatchObject({ frames: 300, fps: 30, renderSeconds: 512.3, gpuSeconds: 571.9, warnings: ["markers ignored"] });
  });

  it("reads every worker error code with its retry flag and user message", () => {
    for (const [code, [retryable, message]] of Object.entries(WORKER_ERRORS)) {
      const it_ = interpretStatus({ status: "FAILED", error: `${code}: x`, output: { status: "failed", job_id: JOB, error_code: code, error_message: message, retryable } }, JOB);
      expect(it_).toMatchObject({ kind: "failed", cancelled: false, result: { errorCode: code, retryable, errorMessage: message } });
    }
  });

  it("falls back to the code in RunPod's `error` when the output is missing, and to INTERNAL otherwise", () => {
    expect(workerCodeFromError("GLB_INVALID: bad magic")).toBe("GLB_INVALID");
    expect(workerCodeFromError("Traceback ...")).toBeNull();
    const a = interpretStatus({ status: "FAILED", error: "ENCODE_FAILED: ffmpeg" }, JOB);
    expect(a).toMatchObject({ result: { errorCode: "ENCODE_FAILED", retryable: true, errorMessage: WORKER_ERRORS.ENCODE_FAILED[1], errorDetail: "ENCODE_FAILED: ffmpeg" } });
    const b = interpretStatus({ status: "FAILED", error: "boom" }, JOB);
    expect(b).toMatchObject({ result: { errorCode: "INTERNAL", retryable: true } });
    const c = interpretStatus({ status: "COMPLETED", output: null }, JOB);
    expect(c).toMatchObject({ kind: "failed", result: { errorCode: "INTERNAL" } });
  });

  it("maps a COMPLETED run whose handler reported failure to a failure", () => {
    const it_ = interpretStatus({ status: "COMPLETED", output: { status: "failed", job_id: JOB, error_code: "GLB_TOO_LARGE" } }, JOB);
    expect(it_).toMatchObject({ kind: "failed", result: { errorCode: "GLB_TOO_LARGE", retryable: false } });
  });

  it("treats RunPod CANCELLED and TIMED_OUT as refundable failures", () => {
    expect(interpretStatus({ status: "CANCELLED" }, JOB)).toMatchObject({ kind: "failed", cancelled: true, result: { errorCode: "RUNPOD_CANCELLED" } });
    expect(interpretStatus({ status: "TIMED_OUT" }, JOB)).toMatchObject({ kind: "failed", cancelled: false, result: { errorCode: "RUNPOD_TIMED_OUT", errorMessage: SITE_ERRORS.RUNPOD_TIMED_OUT[1] } });
  });

  it("ignores payloads for another job and statuses it does not know", () => {
    expect(interpretStatus({ status: "COMPLETED", output: { status: "succeeded", job_id: "other" } }, JOB).kind).toBe("ignore");
    expect(interpretStatus({ status: "WEIRD" }, JOB).kind).toBe("ignore");
  });

  it("maps worker stages onto the studio's statuses (README progress table)", () => {
    expect(["downloading", "ingest", "direct"].map(stageToStatus)).toEqual(["PREPARING", "PREPARING", "PREPARING"]);
    expect(stageToStatus("render")).toBe("RENDERING");
    expect(stageToStatus("encoding")).toBe("ENCODING");
    expect(stageToStatus("uploading")).toBe("UPLOADING");
    expect(rowStatus("queued", null)).toBe("QUEUED");
    expect(rowStatus("running", null)).toBe("PREPARING");
    expect(rowStatus("succeeded", "done")).toBe("COMPLETE");
    expect(rowStatus("failed", "render")).toBe("FAILED");
    expect(rowStatus("cancelled", null)).toBe("CANCELLED");
  });

  it("keeps outputs under the owner's prefix and signs URLs to outlive the job (R2 max 7 days)", () => {
    expect(outputKey("u1", "j1", "video")).toBe("r/u1/j1/video.mp4");
    expect(outputKey("u1", "j1", "poster")).toBe("r/u1/j1/poster.jpg");
    const p = presignLifetimes("final");
    expect(p.putSeconds).toBeGreaterThan(p.getSeconds);
    expect(p.putSeconds).toBeLessThanOrEqual(7 * 24 * 3600);
  });
});

describe("row -> studio job", () => {
  const row = (patch: Partial<RenderJobRow>): RenderJobRow => ({
    id: "j", user_id: "u", project_id: "p", version_id: null, upload_id: "a", kind: "preview", status: "running",
    params: { prompt: "x", tier: "preview", world: "night_street" }, runpod_id: "rp", output_keys: [], cost_credits: 3,
    error: null, error_code: null, retryable: null, stage: "render", frame: 42, total_frames: 300, runpod_status: "IN_PROGRESS",
    outputs: null, video: null, timings: null, warnings: [], render_seconds: null, gpu_seconds: null, delay_ms: null,
    execution_ms: null, attempts: 0, refunded_credits: 0, idempotency_key: "k", created_at: "2026-09-28T12:00:00Z",
    started_at: null, finished_at: null, updated_at: "2026-09-28T12:00:00Z", submitted_at: null, last_polled_at: null, notified_at: null,
    ...patch,
  });

  it("carries progress and params, and a result URL only when complete", () => {
    expect(rowToRenderJob(row({}), { video: "https://v" })).toMatchObject({
      status: "RENDERING", frame: 42, totalFrames: 300, resultUrl: null, target: "cloud", params: { world: "night_street" },
    });
    expect(rowToRenderJob(row({ status: "succeeded", stage: "done" }), { video: "https://v", poster: "https://p" })).toMatchObject({
      status: "COMPLETE", resultUrl: "https://v", posterUrl: "https://p",
    });
  });

  it("shows the user-safe error and refund, never operator detail", () => {
    const j = rowToRenderJob(row({ status: "failed", error: "The render failed.", error_code: "RENDER_FAILED", refunded_credits: 3 }));
    expect(j).toMatchObject({ status: "FAILED", error: "The render failed.", errorCode: "RENDER_FAILED", refundedCredits: 3 });
    expect(JSON.stringify(j)).not.toContain("error_detail");
  });

  it("marks an expired render and drops its URLs; a finished one says when it expires", () => {
    const done = row({ status: "succeeded", stage: "done", finished_at: "2026-09-28T12:00:00Z", retention_days: 7 });
    expect(expiresAtMs(done)).toBe(Date.parse("2026-10-05T12:00:00Z"));
    expect(rowToRenderJob(done, { video: "https://v" })).toMatchObject({ expired: false, resultUrl: "https://v", expiresAt: Date.parse("2026-10-05T12:00:00Z") });
    const gone = rowToRenderJob({ ...done, expired_at: "2026-10-05T12:05:00Z" }, { video: "https://v", poster: "https://p" });
    expect(gone).toMatchObject({ status: "COMPLETE", expired: true, resultUrl: null, posterUrl: null });
    expect(rowToRenderJob(row({})).expiresAt).toBeNull();
  });

  it("never reports a zero frame total (the schema needs a positive count)", () => {
    expect(rowToRenderJob(row({ total_frames: null, frame: 0, status: "queued", stage: null })).totalFrames).toBe(1);
  });
});

describe("migration: plan limits v2", () => {
  const sql = readFileSync(join(import.meta.dirname, "../../supabase/migrations/20260928150000_plan_limits_v2.sql"), "utf8");
  it("debits previews as render_preview and finals as render_final, on the same idempotent ref", () => {
    expect(sql).toContain("case p_kind when 'preview' then 'render_preview' else 'render_final' end");
    expect(sql).toContain("'render:' || v_job.id::text");
  });
  it("enforces the plan inside create_render_job, after the credit lock and the replay check", () => {
    const body = sql.slice(sql.indexOf("create or replace function public.create_render_job"));
    const lock = body.indexOf("lock_user_credits");
    const replay = body.indexOf("idempotency_key = p_idempotency_key");
    const tier = body.indexOf("plan_required");
    const active = body.indexOf("too_many_active");
    expect(lock).toBeGreaterThan(0);
    expect(replay).toBeGreaterThan(lock);
    expect(tier).toBeGreaterThan(replay);
    expect(active).toBeGreaterThan(tier);
    expect(body).toContain("params.watermark is set by the server");
  });
  it("keeps the retention functions service-role only and never security definer", () => {
    for (const fn of ["expired_render_outputs(integer)", "mark_render_outputs_expired(uuid[])", "expire_uploads(integer)", "mark_uploads_purged(uuid[])"]) {
      expect(sql).toContain(`revoke all on function public.${fn} from public, anon, authenticated`);
      expect(sql).toContain(`grant execute on function public.${fn} to service_role`);
    }
    expect(sql).not.toMatch(/security definer/i);
  });
});

describe("migration", () => {
  const sql = readFileSync(join(import.meta.dirname, "../../supabase/migrations/20260928140000_render_pipeline.sql"), "utf8");
  it("keeps the private table unreadable by users and the finish function service-role only", () => {
    expect(sql).toMatch(/alter table public\.render_job_private enable row level security/);
    expect(sql).toMatch(/revoke all on public\.render_job_private from anon, authenticated/);
    expect(sql).toMatch(/grant execute on function public\.finish_render_job\([^)]*\)\s*to service_role/);
    expect(sql).not.toMatch(/security definer/i);
  });
  it("only moves a live job on the same RunPod attempt (idempotency)", () => {
    expect(sql).toContain("and status in ('queued', 'running')");
    expect(sql).toContain("and runpod_id is not distinct from p_runpod_id");
  });
});
