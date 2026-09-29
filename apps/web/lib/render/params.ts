import { z } from "@/lib/zod";
import { WORLD_IDS } from "./worlds";

/**
 * The render request the site sends, mirroring the worker contract
 * (Rendering-worker `worker/contract.py` `parse_params`, `worker/README.md` section 1). Validated in the
 * browser for instant feedback and again, authoritatively, in POST /api/renders.
 * Strict: an unknown key is refused here, as the worker refuses it with INVALID_INPUT.
 */
export const TIERS = ["preview", "final"] as const;
export const ASPECTS = ["9:16", "16:9"] as const;
export const FINISHES = ["gloss", "metallic", "satin", "matte"] as const;
export const MAX_PROMPT = 2000;
/** engine/script.py DURATION_RANGE: what the worker itself accepts. The site sends less (OFFERED_DURATIONS). */
export const DURATION_RANGE = [3, 30] as const;
/**
 * The only clip lengths the site accepts, because renders are priced flat per tier (lib/render/cost.ts) for
 * 8-12 s clips. create_render_job refuses any other `duration` too (20260929200000_storage_security.sql).
 */
export const OFFERED_DURATIONS = [8, 10, 12] as const;
/** A length pinned in the prompt must stay inside what the price assumes. */
export const PROMPT_DURATION_RANGE = [8, 12] as const;
/** engine/director/job.py SEED_LIMIT (exclusive). */
export const SEED_LIMIT = 2 ** 31;

export type RenderTier = (typeof TIERS)[number];
export type RenderAspect = (typeof ASPECTS)[number];
export type PaintFinish = (typeof FINISHES)[number];

const RenderParamsShape = z.object({
  prompt: z.string().max(MAX_PROMPT).refine((s) => !s.includes("\u0000"), "no NUL").default(""),
  world: z.enum(WORLD_IDS).optional(),
  aspect: z.enum(ASPECTS).optional(),
  tier: z.enum(TIERS).default("preview"),
  seed: z.number().int().min(0).max(SEED_LIMIT - 1).optional(),
  duration: z
    .number()
    .refine((d) => (OFFERED_DURATIONS as readonly number[]).includes(d), `must be ${OFFERED_DURATIONS.join(", ")} seconds`)
    .optional(),
  paint: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
  finish: z.enum(FINISHES).optional(),
});

// The worker uses finish only with paint; a finish on its own is a client mistake worth surfacing.
const finishNeedsPaint = { message: "finish needs paint", path: ["finish"] };

// The worker's director reads a clip length and a frame rate pinned in the prompt, and a prompt pin beats
// params.duration (Rendering-worker engine/director/intent.py _DUR / _FPS; its first match wins). Mirrored by
// render_prompt_format_ok() in SQL.
const PROMPT_DURATION = /(?<![\d.])(\d{1,3}(?:\.\d+)?)[\s-]*(?:s|sec|secs|second|seconds)\b/i;
// The engine honours a 25/30/60 fps pin in the prompt; the flat price is set at its 24 fps default.
const PROMPT_FPS_OVER = /\b(25|30|60)\s*fps\b/i;

/** Why a prompt's format pins fall outside the flat price, or null when they don't. */
export function promptFormatIssue(prompt: string): string | null {
  const m = PROMPT_DURATION.exec(prompt);
  if (m) {
    const d = Number(m[1]);
    if (d < PROMPT_DURATION_RANGE[0] || d > PROMPT_DURATION_RANGE[1]) {
      return `the prompt asks for a ${m[1]} s clip; set the length under More options (8, 10 or 12 s) instead`;
    }
  }
  const fps = PROMPT_FPS_OVER.exec(prompt);
  if (fps) return `${fps[1]} fps is not offered; clips render at 24 fps`;
  return null;
}

const promptFormatOk = {
  check: (p: { prompt: string }) => promptFormatIssue(p.prompt) === null,
  issue: (p: { prompt: string }) => ({ message: promptFormatIssue(p.prompt) ?? "prompt format", path: ["prompt"] }),
};

/**
 * What the BROWSER may send. Strict, and without `watermark`: the watermark is the plan's decision, so a request
 * carrying it is refused here (and by create_render_job), never forwarded.
 */
export const RenderParamsSchema = RenderParamsShape.strict()
  .refine((p) => p.finish === undefined || p.paint !== undefined, finishNeedsPaint)
  .superRefine((p, ctx) => {
    if (!promptFormatOk.check(p)) ctx.addIssue({ code: "custom", ...promptFormatOk.issue(p) });
  });

/**
 * What the SERVER sends the worker (`input.params`): the browser's params plus `watermark`, which the server
 * injects from the job row (render_jobs.watermark, stamped from the plan by create_render_job). Mirrors
 * `parse_params` in Rendering-worker `worker/contract.py`, which rejects unknown keys.
 */
export const WorkerParamsSchema = RenderParamsShape.extend({ watermark: z.boolean().optional() })
  .strict()
  .refine((p) => p.finish === undefined || p.paint !== undefined, finishNeedsPaint);
export type WorkerParams = z.infer<typeof WorkerParamsSchema>;

export type RenderParams = z.infer<typeof RenderParamsSchema>;
export type RenderParamsInput = z.input<typeof RenderParamsSchema>;

/**
 * The params exactly as stored on the job and sent to the worker: absent fields dropped (never null), the
 * prompt whitespace-collapsed, paint lower-cased. Stable key order so the idempotency check in
 * create_render_job (params `is distinct from`) sees a retry as the same request.
 */
export function normalizeParams(p: RenderParams): RenderParams {
  const out: RenderParams = { prompt: p.prompt.replace(/\s+/g, " ").trim(), tier: p.tier };
  if (p.world !== undefined) out.world = p.world;
  if (p.aspect !== undefined) out.aspect = p.aspect;
  if (p.seed !== undefined) out.seed = p.seed;
  if (p.duration !== undefined) out.duration = p.duration;
  if (p.paint !== undefined) {
    out.paint = p.paint.toLowerCase();
    out.finish = p.finish ?? "gloss";
  }
  return out;
}

/** Parses untrusted input into normalized params, or a short reason for the user. */
export function parseRenderParams(input: unknown): { ok: true; value: RenderParams } | { ok: false; message: string } {
  const r = RenderParamsSchema.safeParse(input);
  if (!r.success) {
    const issue = r.error.issues[0];
    const field = issue?.path.join(".") || "params";
    return { ok: false, message: `${field}: ${issue?.message ?? "invalid"}` };
  }
  return { ok: true, value: normalizeParams(r.data) };
}
