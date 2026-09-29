import { z } from "@/lib/zod";
import { Environment, Ground, ShotAction, LightingStyle, TimeOfDay, CameraStyle, OutputSchema } from "./scene-plan";

export const EffectKey = z.enum(["rain", "wetGround", "motionBlur", "depthOfField"]);

export const ScenePatchSchema = z.discriminatedUnion("operation", [
  z.object({
    operation: z.literal("update_lighting"),
    exposureDelta: z.number().optional(),
    style: LightingStyle.optional(),
    rim: z.boolean().optional(),
    practicals: z.boolean().optional(),
  }),
  z.object({
    operation: z.literal("modify_camera"),
    shotId: z.string().optional(),
    distanceMultiplier: z.number().positive().optional(),
    heightDelta: z.number().optional(),
    lensMm: z.number().optional(),
    style: CameraStyle.optional(),
    motionStrength: z.number().optional(),
  }),
  z.object({ operation: z.literal("set_shot_action"), shotId: z.string(), action: ShotAction }),
  z.object({ operation: z.literal("set_effect"), effect: EffectKey, value: z.number() }),
  z.object({
    operation: z.literal("set_scene"),
    environment: Environment.optional(),
    time: TimeOfDay.optional(),
    ground: Ground.optional(),
    fogDensity: z.number().optional(),
  }),
  z.object({ operation: z.literal("set_output"), output: OutputSchema.partial() }),
]);

export type ScenePatch = z.infer<typeof ScenePatchSchema>;
export type EffectKey = z.infer<typeof EffectKey>;
