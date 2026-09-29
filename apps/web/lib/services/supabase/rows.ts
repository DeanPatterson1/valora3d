import {
  DEFAULT_PREFS,
  ModelAnalysisSchema,
  ScenePlanSchema,
  UserPrefsSchema,
  type Asset,
  type CreditTransaction,
  type Project,
  type SceneVersion,
  type User,
} from "@/lib/schema";

/** Row shapes as stored in Postgres (supabase/migrations). Pure mappers to the app's schema types. */

export type ProfileRow = {
  id: string;
  email: string;
  name: string;
  avatar_seed: string;
  plan: "free" | "creator" | "pro";
  prefs: unknown;
  created_at: string;
  /** Added by 20260929120000_account.sql; absent on an older database. */
  email_render_ready?: boolean;
  /** Added by 20260930130000_lifecycle.sql; absent on an older database. */
  email_product_tips?: boolean;
};

export type ProjectRow = {
  id: string;
  user_id: string;
  name: string;
  asset_id: string | null;
  analysis: unknown;
  selected_version_id: string | null;
  created_at: string;
  updated_at: string;
};

export type UploadRow = {
  id: string;
  user_id: string;
  project_id: string | null;
  source: "upload" | "sample";
  file_name: string;
  format: "glb" | "gltf" | "fbx" | "obj";
  r2_key: string | null;
  sample_url: string | null;
  size_bytes: number;
  sha256: string | null;
  status: "pending" | "ready" | "rejected";
  reject_reason: string | null;
  created_at: string;
};

export type VersionRow = {
  id: string;
  project_id: string;
  index: number;
  prompt: string;
  parent_id: string | null;
  plan: unknown;
  created_at: string;
};

export type LedgerRow = {
  id: number;
  amount: number;
  reason: string;
  project_id: string | null;
  created_at: string;
};

const ms = (iso: string) => Date.parse(iso);

export function nameFromEmail(email: string): string {
  const word = (email.split("@")[0] ?? "").split(/[._-]/)[0] ?? "";
  return word ? word.charAt(0).toUpperCase() + word.slice(1) : "You";
}

export function profileToUser(row: ProfileRow): User {
  const prefs = UserPrefsSchema.safeParse({ ...DEFAULT_PREFS, ...(isObject(row.prefs) ? row.prefs : {}) });
  return {
    id: row.id,
    email: row.email,
    name: row.name.trim() || nameFromEmail(row.email),
    avatarSeed: row.avatar_seed,
    plan: row.plan,
    createdAt: ms(row.created_at),
    prefs: prefs.success ? prefs.data : DEFAULT_PREFS,
    emailRenderReady: row.email_render_ready !== false,
    emailProductTips: row.email_product_tips !== false,
  };
}

/** Returns null when the stored analysis is unreadable (the caller flags corruption). */
export function rowToProject(row: ProjectRow): { project: Project; corrupt: boolean } {
  let analysis: Project["analysis"] = null;
  let corrupt = false;
  if (row.analysis !== null) {
    const a = ModelAnalysisSchema.safeParse(row.analysis);
    if (a.success) analysis = a.data;
    else corrupt = true;
  }
  return {
    project: {
      id: row.id,
      name: row.name,
      createdAt: ms(row.created_at),
      updatedAt: ms(row.updated_at),
      assetId: row.asset_id,
      analysis,
      selectedVersionId: row.selected_version_id,
    },
    corrupt,
  };
}

export function projectPatchToRow(patch: Partial<Omit<Project, "id" | "createdAt">>): Partial<ProjectRow> {
  const row: Partial<ProjectRow> = {};
  if (patch.name !== undefined) row.name = patch.name;
  if (patch.assetId !== undefined) row.asset_id = patch.assetId;
  if (patch.analysis !== undefined) row.analysis = patch.analysis;
  if (patch.selectedVersionId !== undefined) row.selected_version_id = patch.selectedVersionId;
  return row;
}

export function uploadToAsset(row: UploadRow): Asset {
  return {
    id: row.id,
    projectId: row.project_id ?? "",
    fileName: row.file_name,
    format: row.format,
    sizeBytes: row.size_bytes,
    source: row.source,
    blobKey: row.source === "upload" ? row.r2_key : null,
    sampleUrl: row.sample_url,
    thumbnailKey: null,
  };
}

export function rowToVersion(row: VersionRow): SceneVersion | null {
  const plan = ScenePlanSchema.safeParse(row.plan);
  if (!plan.success) return null;
  return {
    id: row.id,
    projectId: row.project_id,
    index: row.index,
    prompt: row.prompt,
    parentId: row.parent_id,
    plan: plan.data,
    createdAt: ms(row.created_at),
  };
}

const REASONS: Record<string, CreditTransaction["reason"]> = {
  signup_grant: "starting_balance",
  plan_grant: "plan_grant",
  pack_purchase: "pack_purchase",
  scene_generation: "scene_generation",
  prompt_edit: "prompt_edit",
  preview_render: "preview_render",
  render_preview: "render_preview",
  render_final: "render_final",
  render_refund: "render_refund",
  admin_adjustment: "admin_adjustment",
  billing_reversal: "billing_reversal",
  referral_bonus: "referral_bonus",
  referral_reversal: "referral_reversal",
  credit_expiry: "credit_expiry",
};

export function rowToTransaction(row: LedgerRow): CreditTransaction {
  return {
    id: String(row.id),
    amount: row.amount,
    reason: REASONS[row.reason] ?? "admin_adjustment",
    projectId: row.project_id,
    createdAt: ms(row.created_at),
  };
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
