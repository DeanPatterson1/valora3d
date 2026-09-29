import { z } from "zod";
import { RenderDefaultsSchema } from "./scene-plan";

export const Plan = z.enum(["free", "creator", "pro"]);
export type Plan = z.infer<typeof Plan>;

export const UserPrefsSchema = z.object({
  /**
   * Where the Render tab starts: quality tier (Preview 540p / Final 1080p) and format. Older prefs with
   * fps / resolution / quality still parse (mapped to the nearest tier).
   */
  defaultOutput: RenderDefaultsSchema,
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
  /** "Email me when a render is ready" (profiles.email_render_ready). Absent = on. */
  emailRenderReady: z.boolean().optional(),
  /** "Product tips" emails: welcome, first-render nudge, tips, win-back (profiles.email_product_tips). Absent = on. */
  emailProductTips: z.boolean().optional(),
});
export type User = z.infer<typeof UserSchema>;

export const DEFAULT_PREFS: UserPrefs = {
  defaultOutput: { tier: "preview", aspect: "9:16" },
  localAgent: "not_connected",
};
