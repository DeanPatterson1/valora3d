import { readBody } from "@/lib/server/api";
import { SaveVersionBody, saveSceneVersion, supabaseVersionStore } from "@/lib/server/saveVersion";
import { createServiceSupabase, requireUser } from "@/lib/supabase/server";

/**
 * POST /api/projects/:id/versions — saves a scene version and charges it, in one SQL transaction
 * (`save_scene_version`). The body carries the plan and the declared action (generate / edit / adjust), never a
 * price: the server validates the plan, prices the action and makes a project's first version a generation.
 * 402 insufficient_credits (also for any negative balance), 429 rate_limited, 400 invalid_plan / not_an_adjustment.
 * Users have no INSERT on scene_versions, so this is the only way a version is written.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, SaveVersionBody);
  if (body instanceof Response) return body;
  const { id } = await params;
  return saveSceneVersion(supabaseVersionStore(createServiceSupabase(ctx.config)), ctx.user.id, id, body);
}
