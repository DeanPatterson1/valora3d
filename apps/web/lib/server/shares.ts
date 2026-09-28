import type { SupabaseClient } from "@supabase/supabase-js";
import { z } from "zod";
import { outputKey } from "@/lib/render/contract";
import { isShareSlug, newShareSlug } from "@/lib/share/slug";
import { sharePath, type RenderShare } from "@/lib/share/types";
import { apiError } from "@/lib/supabase/server";
import { sqlErrorResponse } from "./api";
import { lookupPublicShare, type PublicShareReader, type PublicShareRow } from "./shareLookup";

/** `public.render_shares` as stored (20260929130000_render_shares.sql). */
export type RenderShareRow = {
  id: string;
  slug: string;
  job_id: string;
  user_id: string;
  show_prompt: boolean;
  created_at: string;
  revoked_at: string | null;
  view_count: number | string;
};

type SqlError = { code?: string; message: string };

/**
 * Data access for share links. The owner-facing reads go through the caller's own RLS client (so a job or a
 * share that is not theirs simply does not exist); writes and the public read go through the service role and
 * the SQL functions, which re-check ownership and state.
 */
export interface ShareStore extends PublicShareReader {
  /** The caller's own job (RLS), or null. */
  ownedJob(jobId: string): Promise<{ id: string; status: string; expired_at?: string | null } | null>;
  /** The caller's live share for a job (RLS), or null. */
  liveShare(jobId: string): Promise<RenderShareRow | null>;
  create(userId: string, jobId: string, slug: string, showPrompt: boolean): Promise<{ row: RenderShareRow } | { error: SqlError }>;
  revoke(userId: string, jobId: string): Promise<number>;
}

export function toRenderShare(row: RenderShareRow): RenderShare {
  return {
    slug: row.slug,
    path: sharePath(row.slug),
    showPrompt: row.show_prompt,
    createdAt: Date.parse(row.created_at),
    viewCount: Number(row.view_count) || 0,
  };
}

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
const isJobId = (id: string) => z.uuid().safeParse(id).success;
const notFound = () => apiError(404, "not_found", "Render not found.");

export const ShareBodySchema = z.object({ show_prompt: z.boolean().default(false) }).strict();

/** GET /api/renders/:id/share: the caller's live link for their render, or null. */
export async function getShare(store: ShareStore, jobId: string): Promise<Response> {
  if (!isJobId(jobId)) return notFound();
  if (!(await store.ownedJob(jobId))) return notFound();
  const row = await store.liveShare(jobId);
  return json({ share: row ? toRenderShare(row) : null });
}

/**
 * POST /api/renders/:id/share: creates the link (or updates show_prompt on the live one). Owner only: the job
 * must be visible through the caller's RLS client, and create_render_share checks the owner again.
 */
export async function createShare(
  store: ShareStore,
  userId: string,
  jobId: string,
  body: z.infer<typeof ShareBodySchema>,
  mint: () => string = newShareSlug,
): Promise<Response> {
  if (!isJobId(jobId)) return notFound();
  const job = await store.ownedJob(jobId);
  if (!job) return notFound();
  if (job.status !== "succeeded" || job.expired_at) {
    return apiError(409, "not_shareable", job.expired_at ? "This render has expired." : "Only a finished render can be shared.");
  }
  // A slug collision (2^-144) is retried once rather than surfaced.
  for (let attempt = 0; attempt < 2; attempt++) {
    const slug = mint();
    if (!isShareSlug(slug)) return apiError(500, "server", "Something went wrong on our side.");
    const r = await store.create(userId, jobId, slug, body.show_prompt);
    if ("row" in r) return json({ share: toRenderShare(r.row) });
    if (r.error.code === "23505" && attempt === 0) continue;
    return shareErrorResponse(r.error);
  }
  return apiError(500, "server", "Something went wrong on our side.");
}

/** DELETE /api/renders/:id/share: stop sharing. Idempotent; not shared is not an error. */
export async function revokeShare(store: ShareStore, userId: string, jobId: string): Promise<Response> {
  if (!isJobId(jobId)) return notFound();
  if (!(await store.ownedJob(jobId))) return notFound();
  await store.revoke(userId, jobId);
  return json({ share: null });
}

export function shareErrorResponse(error: SqlError): Response {
  if (error.code === "P0001" && error.message.startsWith("rate_limited")) {
    return apiError(429, "rate_limited", "You've created a lot of links recently. Try again in an hour.");
  }
  if (error.code === "P0001" && error.message.startsWith("not_shareable")) {
    return apiError(409, "not_shareable", "This render can no longer be shared.");
  }
  return sqlErrorResponse(error);
}

/** Public media links are signed for this long; the redirect itself is cached for less. */
export const SHARE_MEDIA_URL_SECONDS = 900;
const MEDIA = {
  video: { name: "video", type: "video/mp4" },
  poster: { name: "poster", type: "image/jpeg" },
} as const;

export type Presign = (key: string, seconds: number, response: { contentType: string; disposition: string }) => Promise<string>;

/**
 * GET /r/:slug/video|poster: a 302 to a short-lived presigned R2 GET. The browser then talks to R2 directly,
 * so Range requests (seeking) work natively and the Worker never streams the bytes. Revoked or expired: 410.
 */
export async function shareMedia(store: PublicShareReader, presign: Presign | null, slug: string, file: string): Promise<Response> {
  const noindex = { "X-Robots-Tag": "noindex, nofollow" };
  if (!Object.hasOwn(MEDIA, file)) return new Response(null, { status: 404, headers: { ...noindex, "Cache-Control": "no-store" } });
  const found = await lookupPublicShare(store, slug);
  if (found.state === "missing") return new Response(null, { status: 404, headers: { ...noindex, "Cache-Control": "no-store" } });
  if (found.state === "gone") return new Response(null, { status: 410, headers: { ...noindex, "Cache-Control": "public, max-age=300" } });
  if (!presign) return new Response(null, { status: 503, headers: { ...noindex, "Cache-Control": "no-store" } });
  const m = MEDIA[file as keyof typeof MEDIA];
  const url = await presign(outputKey(found.userId, found.jobId, m.name), SHARE_MEDIA_URL_SECONDS, {
    contentType: m.type,
    disposition: "inline",
  });
  return new Response(null, {
    status: 302,
    headers: {
      Location: url,
      // Well inside the signature's life, and short enough that stopping sharing takes effect quickly.
      "Cache-Control": "private, max-age=120",
      "Referrer-Policy": "no-referrer",
      ...noindex,
    },
  });
}

/** ShareStore over Supabase: `user` is the caller's RLS client (null on public paths), `admin` the service role. */
export class SupabaseShareStore implements ShareStore {
  constructor(
    private readonly admin: SupabaseClient,
    private readonly user: SupabaseClient | null = null,
  ) {}

  private userClient(): SupabaseClient {
    if (!this.user) throw new Error("owner reads need the caller's client");
    return this.user;
  }

  async ownedJob(jobId: string) {
    const { data, error } = await this.userClient()
      .from("render_jobs")
      .select("id, status, expired_at")
      .eq("id", jobId)
      .maybeSingle<{ id: string; status: string; expired_at: string | null }>();
    if (error) throw new Error(`render_jobs read failed: ${error.message}`);
    return data;
  }

  async liveShare(jobId: string) {
    const { data, error } = await this.userClient()
      .from("render_shares")
      .select("*")
      .eq("job_id", jobId)
      .is("revoked_at", null)
      .maybeSingle<RenderShareRow>();
    if (error) throw new Error(`render_shares read failed: ${error.message}`);
    return data;
  }

  async create(userId: string, jobId: string, slug: string, showPrompt: boolean) {
    const { data, error } = await this.admin
      .rpc("create_render_share", { p_user_id: userId, p_job_id: jobId, p_slug: slug, p_show_prompt: showPrompt })
      .single<RenderShareRow>();
    if (error || !data) return { error: { code: error?.code, message: error?.message ?? "no row" } };
    return { row: data };
  }

  async revoke(userId: string, jobId: string) {
    const { data, error } = await this.admin.rpc("revoke_render_share", { p_user_id: userId, p_job_id: jobId });
    if (error) throw new Error(`revoke_render_share failed: ${error.message}`);
    return typeof data === "number" ? data : 0;
  }

  async publicRead(slug: string) {
    const { data, error } = await this.admin.rpc("public_render_share", { p_slug: slug }).maybeSingle<PublicShareRow>();
    if (error) throw new Error(`public_render_share failed: ${error.message}`);
    return data;
  }

  async bumpView(slug: string) {
    const { error } = await this.admin.rpc("bump_render_share_view", { p_slug: slug });
    if (error) throw new Error(`bump_render_share_view failed: ${error.message}`);
  }
}
