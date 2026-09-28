import { z } from "zod";
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
/** engine/script.py DURATION_RANGE. The studio offers 8-12 s; the API accepts the engine's whole range. */
export const DURATION_RANGE = [3, 30] as const;
export const OFFERED_DURATIONS = [8, 10, 12] as const;
/** engine/director/job.py SEED_LIMIT (exclusive). */
export const SEED_LIMIT = 2 ** 31;

export type RenderTier = (typeof TIERS)[number];
export type RenderAspect = (typeof ASPECTS)[number];
export type PaintFinish = (typeof FINISHES)[number];

export const RenderParamsSchema = z
  .object({
    prompt: z.string().max(MAX_PROMPT).refine((s) => !s.includes("\u0000"), "no NUL").default(""),
    world: z.enum(WORLD_IDS).optional(),
    aspect: z.enum(ASPECTS).optional(),
    tier: z.enum(TIERS).default("preview"),
    seed: z.number().int().min(0).max(SEED_LIMIT - 1).optional(),
    duration: z.number().min(DURATION_RANGE[0]).max(DURATION_RANGE[1]).optional(),
    paint: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
    finish: z.enum(FINISHES).optional(),
  })
  .strict()
  // The worker uses finish only with paint; a finish on its own is a client mistake worth surfacing.
  .refine((p) => p.finish === undefined || p.paint !== undefined, { message: "finish needs paint", path: ["finish"] });

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
