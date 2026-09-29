import { z } from "zod";
import { Category, ScenePlanSchema } from "./scene-plan";

export const SceneStatsSchema = z.object({
  triangleCount: z.number().int().nonnegative(),
  meshCount: z.number().int().nonnegative(),
  materialCount: z.number().int().nonnegative(),
  objectNames: z.array(z.string()),
  materialNames: z.array(z.string()),
  extents: z.tuple([z.number(), z.number(), z.number()]),
  hasSkeleton: z.boolean(),
  animationClipCount: z.number().int().nonnegative(),
});
export type SceneStats = z.infer<typeof SceneStatsSchema>;

export const UnitGuess = z.enum(["m", "mm", "cm", "in", "unknown"]);

export const ModelAnalysisSchema = z.object({
  category: Category,
  confidence: z.number().min(0).max(1),
  unitGuess: UnitGuess,
  scaleFactor: z.number().positive(),
  dimensionsMeters: z.tuple([z.number(), z.number(), z.number()]),
  parts: z.record(z.string(), z.string()),
  capabilities: z.array(z.string()),
  rigged: z.boolean(),
});
export type ModelAnalysis = z.infer<typeof ModelAnalysisSchema>;

export const AssetSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  fileName: z.string(),
  format: z.enum(["glb", "gltf", "fbx", "obj"]),
  sizeBytes: z.number().int().nonnegative(),
  source: z.enum(["upload", "sample"]),
  blobKey: z.string().nullable(),
  sampleUrl: z.string().nullable(),
  thumbnailKey: z.string().nullable(),
});
export type Asset = z.infer<typeof AssetSchema>;

export const ProjectSchema = z.object({
  id: z.string(),
  name: z.string().min(1),
  createdAt: z.number(),
  updatedAt: z.number(),
  assetId: z.string().nullable(),
  analysis: ModelAnalysisSchema.nullable(),
  selectedVersionId: z.string().nullable(),
});
export type Project = z.infer<typeof ProjectSchema>;

export type ProjectState = "No model" | "Model ready" | "Scene ready";
export function deriveProjectState(p: { assetId: string | null; versionCount: number }): ProjectState {
  if (!p.assetId) return "No model";
  if (p.versionCount === 0) return "Model ready";
  return "Scene ready";
}

export const SceneVersionSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  index: z.number().int().nonnegative(),
  prompt: z.string(),
  parentId: z.string().nullable(),
  plan: ScenePlanSchema,
  createdAt: z.number(),
});
export type SceneVersion = z.infer<typeof SceneVersionSchema>;

export const RenderJobStatus = z.enum(["QUEUED", "PREPARING", "RENDERING", "ENCODING", "UPLOADING", "COMPLETE", "FAILED", "CANCELLED"]);
/** What the site asked the renderer for (lib/render/params.ts is the validated shape). */
export const RenderJobParamsSchema = z.object({
  prompt: z.string(),
  tier: z.enum(["preview", "final"]),
  world: z.string().optional(),
  aspect: z.enum(["9:16", "16:9"]).optional(),
  seed: z.number().int().optional(),
  duration: z.number().optional(),
  paint: z.string().optional(),
  finish: z.string().optional(),
});
export const RenderJobSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  /** The scene version the render started from, when there was one. */
  versionId: z.string().nullable(),
  kind: z.enum(["preview", "final"]),
  target: z.enum(["local", "cloud"]),
  status: RenderJobStatus,
  frame: z.number().int().nonnegative(),
  totalFrames: z.number().int().positive(),
  error: z.string().nullable(),
  resultUrl: z.string().nullable(),
  posterUrl: z.string().nullable().optional(),
  params: RenderJobParamsSchema.optional(),
  errorCode: z.string().nullable().optional(),
  costCredits: z.number().int().nonnegative().optional(),
  /** The outputs were deleted after the plan's retention period: nothing to play or download. */
  expired: z.boolean().optional(),
  /** When the outputs will be (or were) deleted, ms since epoch. Null while the render is live. */
  expiresAt: z.number().nullable().optional(),
  /** Credits handed back after a failure or an early cancel. */
  refundedCredits: z.number().int().nonnegative().optional(),
  createdAt: z.number().optional(),
  finishedAt: z.number().nullable().optional(),
});
export type RenderJob = z.infer<typeof RenderJobSchema>;
export type RenderJobStatus = z.infer<typeof RenderJobStatus>;

export const CreditReason = z.enum([
  "starting_balance", "scene_generation", "prompt_edit", "pack_purchase", "plan_grant",
  "preview_render", "render_preview", "render_final", "render_refund", "admin_adjustment", "billing_reversal",
  "referral_bonus", "referral_reversal", "credit_expiry",
]);
export const CreditTransactionSchema = z.object({
  id: z.string(),
  amount: z.number().int(),
  reason: CreditReason,
  projectId: z.string().nullable(),
  createdAt: z.number(),
});
export type CreditTransaction = z.infer<typeof CreditTransactionSchema>;
