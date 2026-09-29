import { buildExport, supabaseReaders } from "@/lib/server/dataExport";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

/**
 * GET /api/account/export — "Download my data" (Settings -> Account): a JSON file of the caller's profile, preferences,
 * projects and scene versions, models (metadata), render jobs, share links, credit ledger, subscriptions, payments,
 * feedback and the emails we sent them. Generated on the server from their own rows (lib/server/dataExport.ts); one
 * export per account per 24 hours (`claim_data_export`). Same-site only (Sec-Fetch-Site), never cached.
 */
export async function GET(request: Request) {
  const site = request.headers.get("sec-fetch-site");
  if (site && site !== "same-origin" && site !== "none") return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const admin = createServiceSupabase(ctx.config);

  let doc: Record<string, unknown>;
  try {
    const { userRead, serviceRead } = supabaseReaders(ctx.userClient, admin);
    doc = await buildExport(
      ctx.user.id,
      async () => await ctx.userClient.from("profiles").select("*").eq("id", ctx.user.id).maybeSingle<Record<string, unknown>>(),
      userRead,
      serviceRead,
    );
  } catch {
    return apiError(500, "server", "Couldn't prepare your data. Try again in a minute.");
  }
  const claimed = await admin.rpc("claim_data_export", { p_user_id: ctx.user.id });
  if (claimed.error) return apiError(500, "server", "Couldn't prepare your data. Try again in a minute.");
  if (claimed.data !== true) return apiError(429, "rate_limited", "You can download your data once a day. Try again tomorrow.");

  const day = new Date().toISOString().slice(0, 10);
  return new Response(JSON.stringify(doc, null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": `attachment; filename="valora3d-data-${day}.json"`,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
