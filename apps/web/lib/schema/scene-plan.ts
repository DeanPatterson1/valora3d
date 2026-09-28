import { z } from "zod";
import { ASPECTS, OFFERED_DURATIONS, TIERS, type RenderTier } from "@/lib/render/params";

export const Environment = z.enum(["studio_black", "studio_white", "outdoor_road", "urban_night"]);
export const Ground = z.enum(["studio_floor", "dry_asphalt", "wet_asphalt", "concrete"]);
export const ShotAction = z.enum(["slow_orbit", "hero_push_in", "low_tracking", "handheld_walk_toward"]);
export const LightingStyle = z.enum(["soft_studio", "dramatic_three_point", "night_city", "sunset", "overcast"]);
export const TimeOfDay = z.enum(["day", "dusk", "night"]);
export const CameraStyle = z.enum(["smooth", "handheld"]);
export const Category = z.enum(["car", "product"]);
/** What the render worker actually produces (lib/render/params.ts): Preview = 540p, Final = 1080p. No 4K. */
export const Tier = z.enum(TIERS);
export const Aspect = z.enum(ASPECTS);
/** The lengths the Render tab offers (OFFERED_DURATIONS). */
export const DurationS = z.union([z.literal(OFFERED_DURATIONS[0]), z.literal(OFFERED_DURATIONS[1]), z.literal(OFFERED_DURATIONS[2])]);
export type DurationS = z.infer<typeof DurationS>;

export const ShotSchema = z.object({
  id: z.string().min(1),
  start: z.number().min(0),
  end: z.number().min(0),
  action: ShotAction,
  distanceMultiplier: z.number().min(0.4).max(2.5),
});

/**
 * A scene's output. `tier` / `aspect` are only set when the prompt asked for them ("4k", "vertical"); unset,
 * the Render tab starts from the user's Settings defaults. fps / resolution / quality are gone: the worker
 * never took them (older stored plans still parse, see `migrateOutput`).
 */
export const OutputSchema = z.object({
  durationS: DurationS,
  tier: Tier.optional().catch(undefined),
  aspect: Aspect.optional().catch(undefined),
});

/** The Render tab's defaults, stored on the user (Settings -> Rendering). */
export const RenderDefaultsShape = z.object({
  tier: Tier.catch("preview"),
  aspect: Aspect.catch("9:16"),
});

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** Nearest offered length, for durations stored before lengths were limited to what the worker renders. */
export function nearestDuration(n: number): DurationS {
  return OFFERED_DURATIONS.reduce<DurationS>((best, d) => (Math.abs(d - n) < Math.abs(best - n) ? d : best), 10);
}

/**
 * The tier a retired output field meant. 720p / 540p / draft -> Preview (540p is the nearer supported size);
 * 1080p and above (1440p, 4K) or standard+ quality -> Final (1080p, the most the worker renders).
 */
export function tierFromLegacy(o: Record<string, unknown>): RenderTier | undefined {
  const res = typeof o.resolution === "string" ? o.resolution.toLowerCase() : null;
  if (res) {
    const px = res === "4k" ? 2160 : Number.parseInt(res, 10);
    if (Number.isFinite(px)) return px >= 1080 ? "final" : "preview";
  }
  if (typeof o.quality === "string") return o.quality === "draft" ? "preview" : "final";
  return undefined;
}

/** Maps a stored output (current or retired shape) onto the current one; unknown input passes through to fail. */
export function migrateOutput(raw: unknown): unknown {
  if (!isRecord(raw)) return raw;
  const { fps: _fps, resolution: _res, quality: _q, ...rest } = raw;
  const out: Record<string, unknown> = { ...rest };
  if (typeof raw.durationS === "number") out.durationS = nearestDuration(raw.durationS);
  if (out.tier === undefined) {
    const t = tierFromLegacy(raw);
    if (t) out.tier = t;
  }
  return out;
}

/** Settings defaults, accepting the retired `{ fps, durationS, resolution, quality }` prefs. */
export const RenderDefaultsSchema = z.preprocess((raw) => {
  if (!isRecord(raw)) return raw;
  return raw.tier === undefined ? { ...raw, tier: tierFromLegacy(raw) } : raw;
}, RenderDefaultsShape);
export type RenderDefaults = z.infer<typeof RenderDefaultsShape>;

/** Migrates the output and, when its length moved to the nearest offered one, rescales the shots with it. */
export function migratePlan(raw: unknown): unknown {
  if (!isRecord(raw) || !isRecord(raw.output)) return raw;
  const output = migrateOutput(raw.output) as Record<string, unknown>;
  const prev = raw.output.durationS;
  const next = output.durationS;
  let shots = raw.shots;
  if (typeof prev === "number" && typeof next === "number" && prev > 0 && prev !== next && Array.isArray(shots) && shots.length) {
    const k = next / prev;
    shots = shots.map((s: unknown, i: number, all: unknown[]) =>
      isRecord(s) && typeof s.start === "number" && typeof s.end === "number"
        ? { ...s, start: s.start * k, end: i === all.length - 1 ? next : s.end * k }
        : s,
    );
  }
  return { ...raw, output, shots };
}

const ScenePlanShape = z
  .object({
    scene: z.object({
      environment: Environment,
      time: TimeOfDay,
      ground: Ground,
      fogDensity: z.number().min(0).max(0.1),
    }),
    subject: z.object({
      category: Category,
      position: z.tuple([z.number(), z.number(), z.number()]),
      motion: z.literal("stationary"),
    }),
    camera: z.object({
      style: CameraStyle,
      lensMm: z.number().min(18).max(135),
      heightM: z.number().min(0.2).max(3),
      motionStrength: z.number().min(0).max(1),
    }),
    shots: z.array(ShotSchema).min(1).max(2),
    lighting: z.object({
      style: LightingStyle,
      exposure: z.number().min(-3).max(3),
      rim: z.boolean(),
      practicals: z.boolean(),
    }),
    effects: z.object({
      rain: z.number().min(0).max(1),
      wetGround: z.number().min(0).max(1),
      motionBlur: z.number().min(0).max(1),
      depthOfField: z.number().min(0).max(1),
    }),
    output: OutputSchema,
  })
  .superRefine((plan, ctx) => {
    const eps = 1e-6;
    let cursor = 0;
    for (const shot of plan.shots) {
      if (Math.abs(shot.start - cursor) > eps || shot.end <= shot.start) {
        ctx.addIssue({ code: "custom", path: ["shots"], message: "shots must be contiguous" });
        return;
      }
      cursor = shot.end;
    }
    if (Math.abs(cursor - plan.output.durationS) > eps) {
      ctx.addIssue({ code: "custom", path: ["shots"], message: "shots must end at output.durationS" });
    }
  });

/** A scene plan; older stored plans (4K, 30 s, fps...) are migrated to the nearest supported values. */
export const ScenePlanSchema = z.preprocess(migratePlan, ScenePlanShape);

export type ScenePlan = z.infer<typeof ScenePlanSchema>;
export type Category = z.infer<typeof Category>;
export type Shot = z.infer<typeof ShotSchema>;
export type ScenePlanOutput = z.infer<typeof OutputSchema>;
