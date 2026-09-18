import { z } from "zod";
import { OutputSchema } from "./scene-plan";

export const Plan = z.enum(["free", "creator", "pro"]);
export type Plan = z.infer<typeof Plan>;

export const UserPrefsSchema = z.object({
  /** Output settings a new scene should start from. Not yet wired into `defaultPlan` (follow-up). */
  defaultOutput: OutputSchema,
  /** The desktop render agent is not part of the prototype; only this value exists. */
  localAgent: z.literal("not_connected"),
});
export type UserPrefs = z.infer<typeof UserPrefsSchema>;

export const UserSchema = z.object({
  id: z.string().min(1),
  email: z.string().min(1),
  name: z.string().min(1),
  /** Seeds the deterministic monochrome avatar; stable for the life of the account. */
  avatarSeed: z.string().min(1),
  plan: Plan,
  createdAt: z.number(),
  prefs: UserPrefsSchema,
});
export type User = z.infer<typeof UserSchema>;

export const DEFAULT_PREFS: UserPrefs = {
  defaultOutput: { fps: 30, durationS: 10, resolution: "1080p", quality: "high" },
  localAgent: "not_connected",
};
