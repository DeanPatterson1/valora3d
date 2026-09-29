import { serverConfig } from "@/lib/env";
import { flag } from "@/lib/flags/flags";
import { R2Storage } from "@/lib/server/r2";
import { shareMedia } from "@/lib/server/shares";
import { createPublicShareReader } from "@/lib/server/shareLookup";

/**
 * GET /r/:slug/video|poster — the shared render's file: a 302 to a short-lived presigned R2 link (Range
 * requests for seeking go straight to R2). 404 for an unknown link, 410 once revoked or expired.
 */
export async function GET(_request: Request, { params }: { params: Promise<{ slug: string; file: string }> }) {
  const { slug, file } = await params;
  const config = serverConfig();
  // No backend, or sharing switched off (feature_flags.sharing_enabled): the file is not served.
  if (!config || !(await flag("sharing_enabled"))) {
    return new Response(null, { status: 404, headers: { "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow" } });
  }
  const r2 = config.r2 ? new R2Storage(config.r2) : null;
  return shareMedia(createPublicShareReader(config), r2 ? (key, seconds, response) => r2.presignGet(key, seconds, response) : null, slug, file);
}
