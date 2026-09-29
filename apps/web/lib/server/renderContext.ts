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

/** The poster in the render-ready mail stays viewable this long (the SigV4 presign maximum). */
export const MAIL_POSTER_SECONDS = 7 * 24 * 3600;

export function createNotifier(config: ServerConfig, admin: SupabaseClient): RenderNotifier {
  if (!config.email) return noopNotifier;
  return new ResendNotifier(config.email, async (userId, jobId) => {
    const [{ data: profile }, { data: job }] = await Promise.all([
      admin
        .from("profiles")
        .select("email, name, email_render_ready")
        .eq("id", userId)
        .maybeSingle<{ email: string; name: string; email_render_ready: boolean | null }>(),
      admin
        .from("render_jobs")
        .select("project_id, kind, status, expired_at, projects(name)")
        .eq("id", jobId)
        .eq("user_id", userId)
        .maybeSingle<{ project_id: string; kind: "preview" | "final"; status: string; expired_at: string | null; projects: { name: string } | null }>(),
    ]);
    if (!profile?.email || !job) return null;
    if (profile.email_render_ready === false) return { email: profile.email, name: profile.name, projectId: job.project_id, projectName: "", emailRenderReady: false };
    const posterUrl =
      config.r2 && job.status === "succeeded" && !job.expired_at
        ? await new R2Storage(config.r2)
            .presignGet(outputKey(userId, jobId, "poster"), MAIL_POSTER_SECONDS, { contentType: "image/jpeg", disposition: "inline" })
            .catch(() => null)
        : null;
    return {
      email: profile.email,
      name: profile.name,
      projectId: job.project_id,
      projectName: job.projects?.name ?? "your project",
      emailRenderReady: true,
      posterUrl,
      kind: job.kind,
    };
  });
}

/** How long a playback / download link stays valid. */
export const RESULT_URL_SECONDS = 3600;

/** A finished job's short-lived playback URLs (inline), or none. */
export async function resultUrls(config: ServerConfig, row: RenderJobRow): Promise<{ video: string | null; poster: string | null }> {
  if (row.status !== "succeeded" || row.expired_at || !config.r2) return { video: null, poster: null };
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
