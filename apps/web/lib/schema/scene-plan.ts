import { z } from "zod";

export const Environment = z.enum(["studio_black", "studio_white", "outdoor_road", "urban_night"]);
export const Ground = z.enum(["studio_floor", "dry_asphalt", "wet_asphalt", "concrete"]);
export const ShotAction = z.enum(["slow_orbit", "hero_push_in", "low_tracking", "handheld_walk_toward"]);
export const LightingStyle = z.enum(["soft_studio", "dramatic_three_point", "night_city", "sunset", "overcast"]);
export const TimeOfDay = z.enum(["day", "dusk", "night"]);
export const CameraStyle = z.enum(["smooth", "handheld"]);
export const Category = z.enum(["car", "product"]);
export const Resolution = z.enum(["720p", "1080p", "1440p", "4k"]);
export const Quality = z.enum(["draft", "standard", "high", "ultra"]);
export const Fps = z.union([z.literal(24), z.literal(30), z.literal(60)]);
export const DurationS = z.union([z.literal(5), z.literal(10), z.literal(15), z.literal(30)]);

export const ShotSchema = z.object({
  id: z.string().min(1),
  start: z.number().min(0),
  end: z.number().min(0),
  action: ShotAction,
  distanceMultiplier: z.number().min(0.4).max(2.5),
});

export const OutputSchema = z.object({
  fps: Fps,
  durationS: DurationS,
  resolution: Resolution,
  quality: Quality,
});

export const ScenePlanSchema = z
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

export type ScenePlan = z.infer<typeof ScenePlanSchema>;
export type Category = z.infer<typeof Category>;
export type Shot = z.infer<typeof ShotSchema>;
export type ScenePlanOutput = z.infer<typeof OutputSchema>;
