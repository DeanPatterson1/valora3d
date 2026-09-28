import type { SupabaseClient } from "@supabase/supabase-js";
import type { ServerConfig } from "@/lib/env";
import { outputKey } from "@/lib/render/contract";
import { rowToRenderJob, type RenderJobRow } from "@/lib/render/jobRow";
import type { RenderJob } from "@/lib/schema";
import { createServiceSupabase } from "@/lib/supabase/server";
import { noopNotifier, ResendNotifier, type RenderNotifier } from "./notify";
import { R2Storage } from "./r2";
import { RenderPipeline } from "./renderPipeline";
import { SupabaseRenderStore } from "./renderStore";
import { RunpodClient } from "./runpod";

/** Server-only wiring of the render pipeline from the Worker's env. */
export function createRenderPipeline(config: ServerConfig, admin: SupabaseClient = createServiceSupabase(config)): RenderPipeline {
  return new RenderPipeline({
    store: new SupabaseRenderStore(admin),
    runpod: config.runpod ? new RunpodClient(config.runpod) : null,
    r2: config.r2 ? new R2Storage(config.r2) : null,
    notifier: createNotifier(config, admin),
  });
}

export function createNotifier(config: ServerConfig, admin: SupabaseClient): RenderNotifier {
  if (!config.email) return noopNotifier;
  return new ResendNotifier(config.email, async (userId, jobId) => {
    const [{ data: profile }, { data: job }] = await Promise.all([
      admin.from("profiles").select("email, name").eq("id", userId).maybeSingle<{ email: string; name: string }>(),
      admin.from("render_jobs").select("project_id, projects(name)").eq("id", jobId).maybeSingle<{ project_id: string; projects: { name: string } | null }>(),
    ]);
    if (!profile?.email || !job) return null;
    return { email: profile.email, name: profile.name, projectId: job.project_id, projectName: job.projects?.name ?? "your project" };
  });
}

/** How long a playback / download link stays valid. */
export const RESULT_URL_SECONDS = 3600;

/** A finished job's short-lived playback URLs (inline), or none. */
export async function resultUrls(config: ServerConfig, row: RenderJobRow): Promise<{ video: string | null; poster: string | null }> {
  if (row.status !== "succeeded" || !config.r2) return { video: null, poster: null };
  const r2 = new R2Storage(config.r2);
  const [video, poster] = await Promise.all([
    r2.presignGet(outputKey(row.user_id, row.id, "video"), RESULT_URL_SECONDS, { contentType: "video/mp4", disposition: "inline" }),
    r2.presignGet(outputKey(row.user_id, row.id, "poster"), RESULT_URL_SECONDS, { contentType: "image/jpeg", disposition: "inline" }),
  ]);
  return { video, poster };
}

export async function toClientJob(config: ServerConfig, row: RenderJobRow): Promise<RenderJob> {
  return rowToRenderJob(row, await resultUrls(config, row));
}
