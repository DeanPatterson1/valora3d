import { publicFlags } from "@/lib/flags/flags";
import { serverConfig } from "@/lib/env";
import { createRequestSupabase } from "@/lib/supabase/server";

/**
 * GET /api/flags — the kill switches as they apply to the caller: `{ flags: { renders_enabled: true, ... } }`.
 * Only on/off values; rollout lists, settings and who changed what stay server-side. Evaluated for the signed-in
 * account when there is one (rollouts bucket by user id). Cached privately for 30 s, like the server's own copy.
 * Local mode answers every switch on.
 */
export async function GET(request: Request) {
  let userId: string | null = null;
  const config = serverConfig();
  if (config && /(?:^|;\s*)sb-[^=]+-auth-token/.test(request.headers.get("cookie") ?? "")) {
    try {
      const { data } = await (await createRequestSupabase(config)).auth.getUser();
      userId = data.user?.id ?? null;
    } catch {
      userId = null;
    }
  }
  return Response.json(
    { flags: await publicFlags(userId) },
    { headers: { "Cache-Control": "private, max-age=30", Vary: "Cookie" } },
  );
}
