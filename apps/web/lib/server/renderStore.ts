import type { SupabaseClient } from "@supabase/supabase-js";
import type { RenderJobRow } from "@/lib/render/jobRow";
import type { PlanId } from "@/lib/render/planLimits";
import type { CreateJobArgs, FinishArgs, LivePatch, PrivatePatch, RenderStore, StoreError, UploadForRender } from "./renderPipeline";

const LIVE = ["queued", "running"] as const;

/**
 * RenderStore over the SERVICE-ROLE client (bypasses RLS). Only constructed inside API routes after the
 * caller is resolved (or the webhook token / cron secret is verified); ownership checks happen in the routes
 * and in create_render_job itself.
 */
export class SupabaseRenderStore implements RenderStore {
  constructor(private readonly admin: SupabaseClient) {}

  async getJob(id: string): Promise<RenderJobRow | null> {
    const { data, error } = await this.admin.from("render_jobs").select("*").eq("id", id).maybeSingle<RenderJobRow>();
    if (error) throw new Error(`render_jobs read failed: ${error.message}`);
    return data;
  }

  async findByIdempotencyKey(userId: string, key: string): Promise<RenderJobRow | null> {
    const { data, error } = await this.admin
      .from("render_jobs")
      .select("*")
      .eq("user_id", userId)
      .eq("idempotency_key", key)
      .maybeSingle<RenderJobRow>();
    if (error) throw new Error(`render_jobs read failed: ${error.message}`);
    return data;
  }

  async getWebhookHash(jobId: string): Promise<string | null> {
    const { data } = await this.admin
      .from("render_job_private")
      .select("webhook_token_hash")
      .eq("job_id", jobId)
      .maybeSingle<{ webhook_token_hash: string }>();
    return data?.webhook_token_hash ?? null;
  }

  async createJob(args: CreateJobArgs): Promise<{ row: RenderJobRow } | { error: StoreError }> {
    const { data, error } = await this.admin
      .rpc("create_render_job", {
        p_user_id: args.userId,
        p_project_id: args.projectId,
        p_version_id: args.versionId,
        p_upload_id: args.uploadId,
        p_kind: args.kind,
        p_params: args.params,
        p_cost: args.cost,
        p_idempotency_key: args.idempotencyKey,
      })
      .single<RenderJobRow>();
    if (error || !data) return { error: { code: error?.code, message: error?.message ?? "no row" } };
    return { row: data };
  }

  async putPrivate(jobId: string, patch: PrivatePatch): Promise<void> {
    if (patch.webhook_token_hash) {
      const { error } = await this.admin.from("render_job_private").upsert({ job_id: jobId, ...patch }, { onConflict: "job_id" });
      if (error) throw new Error(`render_job_private write failed: ${error.message}`);
      return;
    }
    // Operator detail only ever lands on an existing row (the hash is written first, at submit).
    const { error } = await this.admin.from("render_job_private").update(patch).eq("job_id", jobId);
    if (error) throw new Error(`render_job_private write failed: ${error.message}`);
  }

  async markSubmitted(jobId: string, runpodId: string, runpodStatus: string): Promise<boolean> {
    const now = new Date().toISOString();
    const { data, error } = await this.admin
      .from("render_jobs")
      .update({ runpod_id: runpodId, runpod_status: runpodStatus.slice(0, 32), submitted_at: now, last_polled_at: now })
      .eq("id", jobId)
      .is("runpod_id", null)
      .in("status", LIVE)
      .select("id");
    if (error) throw new Error(`render_jobs submit write failed: ${error.message}`);
    return (data ?? []).length === 1;
  }

  async updateLive(jobId: string, runpodId: string, patch: LivePatch): Promise<void> {
    const { error } = await this.admin.from("render_jobs").update(patch).eq("id", jobId).eq("runpod_id", runpodId).in("status", LIVE);
    if (error) throw new Error(`render_jobs progress write failed: ${error.message}`);
  }

  async finish(args: FinishArgs): Promise<number> {
    const { data, error } = await this.admin.rpc("finish_render_job", {
      p_job_id: args.jobId,
      p_runpod_id: args.runpodId,
      p_status: args.status,
      p_error: args.error,
      p_error_code: args.errorCode,
      p_retryable: args.retryable,
      p_result: args.result,
      p_refund: args.refund,
    });
    if (error) throw new Error(`finish_render_job failed: ${error.message}`);
    return typeof data === "number" ? data : -1;
  }

  async claimRetry(jobId: string, oldRunpodId: string, attempts: number): Promise<boolean> {
    const { data, error } = await this.admin
      .from("render_jobs")
      .update({ runpod_id: null, attempts: attempts + 1, status: "queued", stage: null, frame: 0, submitted_at: null, runpod_status: null })
      .eq("id", jobId)
      .eq("runpod_id", oldRunpodId)
      .eq("attempts", attempts)
      .in("status", LIVE)
      .select("id");
    if (error) throw new Error(`render_jobs retry claim failed: ${error.message}`);
    return (data ?? []).length === 1;
  }

  async listStale(updatedBefore: string, limit: number): Promise<RenderJobRow[]> {
    const { data, error } = await this.admin
      .from("render_jobs")
      .select("*")
      .in("status", LIVE)
      .lt("updated_at", updatedBefore)
      .order("updated_at", { ascending: true })
      .limit(limit);
    if (error) throw new Error(`render_jobs sweep read failed: ${error.message}`);
    return (data ?? []) as RenderJobRow[];
  }

  async markNotified(jobId: string): Promise<void> {
    await this.admin.from("render_jobs").update({ notified_at: new Date().toISOString() }).eq("id", jobId);
  }

  async getUpload(uploadId: string, userId: string): Promise<UploadForRender | null> {
    const { data } = await this.admin
      .from("uploads")
      .select("id, user_id, status, source, r2_key, sample_url")
      .eq("id", uploadId)
      .eq("user_id", userId)
      .maybeSingle<UploadForRender>();
    return data;
  }

  async getPlan(userId: string): Promise<PlanId> {
    // TODO(lane C merge): read the billing lane's plan_limits(plan) instead of the profile's plan alone.
    const { data } = await this.admin.from("profiles").select("plan").eq("id", userId).maybeSingle<{ plan: PlanId }>();
    return data?.plan ?? "free";
  }

  async countActive(userId: string): Promise<number> {
    const { count } = await this.admin
      .from("render_jobs")
      .select("id", { count: "exact", head: true })
      .eq("user_id", userId)
      .in("status", LIVE);
    return count ?? 0;
  }

  async countSince(userId: string, sinceIso: string): Promise<number> {
    const { count } = await this.admin
      .from("render_jobs")
      .select("id", { count: "exact", head: true })
      .eq("user_id", userId)
      .gte("created_at", sinceIso);
    return count ?? 0;
  }
}
