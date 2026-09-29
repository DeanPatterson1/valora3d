import { z } from "zod";
import { json, requireAdmin } from "@/lib/server/admin";
import { findUsers } from "@/lib/server/adminQueries";
import { apiError } from "@/lib/supabase/server";

const Query = z.string().trim().max(200);

/** GET /api/admin/users?q= — users whose email contains q (or whose id is q); newest first. Admins only. */
export async function GET(request: Request) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const q = Query.safeParse(new URL(request.url).searchParams.get("q") ?? "");
  if (!q.success) return apiError(400, "invalid_request", "Search is too long.");
  try {
    return json({ users: await findUsers(ctx.admin, q.data) });
  } catch {
    return apiError(500, "server", "Could not search users.");
  }
}
