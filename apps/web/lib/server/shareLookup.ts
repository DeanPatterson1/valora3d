import { createClient } from "@supabase/supabase-js";
import type { ServerConfig } from "@/lib/env";
import { videoSize } from "@/lib/share/public";
import { isShareSlug } from "@/lib/share/slug";
import type { PublicShareLookup } from "@/lib/share/types";

/**
 * The public read of a share link. Kept free of `next/headers` (no cookies, no user) so the proxy can use it
 * to answer a revoked or expired link with a real 410 before any page renders.
 */

/** One row of public_render_share(slug) (20260929130000_render_shares.sql). */
export type PublicShareRow = {
  state: "live" | "revoked" | "expired";
  job_id: string | null;
  user_id: string | null;
  kind: "preview" | "final" | null;
  prompt: string | null;
  aspect: string | null;
  width: number | null;
  height: number | null;
};

export interface PublicShareReader {
  publicRead(slug: string): Promise<PublicShareRow | null>;
  bumpView(slug: string): Promise<void>;
}

/** The public page's view of a slug. Malformed slugs never reach the database. */
export async function lookupPublicShare(store: Pick<PublicShareReader, "publicRead">, slug: string): Promise<PublicShareLookup> {
  if (!isShareSlug(slug)) return { state: "missing" };
  const row = await store.publicRead(slug);
  if (!row) return { state: "missing" };
  if (row.state === "revoked" || row.state === "expired") return { state: "gone", reason: row.state };
  if (row.state !== "live" || !row.job_id || !row.user_id || (row.kind !== "preview" && row.kind !== "final")) return { state: "missing" };
  const prompt = row.prompt?.trim() || null;
  return {
    state: "live",
    jobId: row.job_id,
    userId: row.user_id,
    share: { slug, kind: row.kind, prompt, ...videoSize(row.kind, row.aspect, row.width, row.height) },
  };
}

/** Service-role reader limited to the two public SQL functions. Server-only. */
export function createPublicShareReader(config: ServerConfig): PublicShareReader {
  const admin = createClient(config.supabase.url, config.supabase.serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
  return {
    async publicRead(slug) {
      const { data, error } = await admin.rpc("public_render_share", { p_slug: slug }).maybeSingle<PublicShareRow>();
      if (error) throw new Error(`public_render_share failed: ${error.message}`);
      return data;
    },
    async bumpView(slug) {
      const { error } = await admin.rpc("bump_render_share_view", { p_slug: slug });
      if (error) throw new Error(`bump_render_share_view failed: ${error.message}`);
    },
  };
}
