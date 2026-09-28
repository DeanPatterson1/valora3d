import type { SupabaseClient } from "@supabase/supabase-js";
import { z } from "zod";
import { ScenePlanSchema } from "@/lib/schema";
import { isFreeAdjustment, VERSION_ACTIONS, type VersionAction } from "@/lib/scene/versionAction";
import type { VersionRow } from "@/lib/services/supabase/rows";
import { apiError } from "@/lib/supabase/server";
import { sqlErrorResponse } from "./api";

/** POST /api/projects/:id/versions body. The browser declares an action; it never sends a price. */
export const SaveVersionBody = z.object({
  prompt: z.string().max(2000),
  parentId: z.uuid().nullable(),
  plan: z.unknown(),
  action: z.enum(VERSION_ACTIONS),
  /** Same key => same version, charged once (a retried save). */
  idempotencyKey: z.string().regex(/^[A-Za-z0-9_-]{8,128}$/),
});
export type SaveVersionInput = z.infer<typeof SaveVersionBody>;

export type SaveVersionArgs = {
  userId: string;
  projectId: string;
  parentId: string | null;
  prompt: string;
  plan: unknown;
  action: VersionAction;
  idempotencyKey: string;
};

export type SavedVersion = { version: VersionRow; charged: number; balance: number; replay: boolean };
export type StoreError = { code?: string; message: string };

/** The two database calls the save makes (service role). `null` parent plan = no such version in this project. */
export interface VersionStore {
  getParentPlan(userId: string, projectId: string, parentId: string): Promise<{ plan: unknown } | null>;
  /** `public.save_scene_version`: charges and inserts in one transaction. */
  save(args: SaveVersionArgs): Promise<{ data: SavedVersion } | { error: StoreError }>;
}

const UUID = z.uuid();

/**
 * Validates the plan with the scene schema, checks that a free "adjust" really only moves the free controls,
 * then lets `save_scene_version` resolve the action (first version = generate), price it, enforce the balance and
 * the hourly cap, and insert: all server-side.
 */
export async function saveSceneVersion(store: VersionStore, userId: string, projectId: string, body: SaveVersionInput): Promise<Response> {
  if (!UUID.safeParse(projectId).success) return apiError(404, "not_found", "Project not found.");
  const plan = ScenePlanSchema.safeParse(body.plan);
  if (!plan.success) return apiError(400, "invalid_plan", "That scene could not be saved: its settings are not valid.");

  if (body.action === "adjust" && body.parentId) {
    const parent = await store.getParentPlan(userId, projectId, body.parentId);
    if (!parent) return apiError(404, "not_found", "The version you changed was not found. Reload the project.");
    const base = ScenePlanSchema.safeParse(parent.plan);
    if (!base.success || !isFreeAdjustment(base.data, plan.data)) {
      return apiError(400, "not_an_adjustment", "That change needs a prompt edit, not a free adjustment.");
    }
  }

  const r = await store.save({
    userId,
    projectId,
    parentId: body.parentId,
    prompt: body.prompt,
    plan: plan.data,
    action: body.action,
    idempotencyKey: body.idempotencyKey,
  });
  if ("error" in r) return sqlErrorResponse(r.error);
  return Response.json(r.data, { status: r.data.replay ? 200 : 201, headers: { "Cache-Control": "no-store" } });
}

/** The VersionStore on the service-role client (the route's only database access). */
export function supabaseVersionStore(admin: SupabaseClient): VersionStore {
  return {
    async getParentPlan(userId, projectId, parentId) {
      const { data } = await admin
        .from("scene_versions")
        .select("plan")
        .eq("id", parentId)
        .eq("project_id", projectId)
        .eq("user_id", userId)
        .maybeSingle<{ plan: unknown }>();
      return data ?? null;
    },
    async save(a) {
      const { data, error } = await admin.rpc("save_scene_version", {
        p_user_id: a.userId,
        p_project_id: a.projectId,
        p_parent_id: a.parentId,
        p_prompt: a.prompt,
        p_plan: a.plan,
        p_action: a.action,
        p_idempotency_key: a.idempotencyKey,
      });
      if (error) return { error };
      return { data: data as SavedVersion };
    },
  };
}
