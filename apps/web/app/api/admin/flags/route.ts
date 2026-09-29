import type { FeatureFlagRow } from "@/lib/admin/types";
import { emailsFor } from "@/lib/server/adminQueries";
import { json, requireAdmin } from "@/lib/server/admin";
import { apiError } from "@/lib/supabase/server";

/** GET /api/admin/flags — every kill switch and setting, with who changed it last. Admins only. */
export async function GET() {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const { data, error } = await ctx.admin
    .from("feature_flags")
    .select("key, description, kind, enabled, rollout_percent, allowlist, value, updated_by, updated_at")
    .order("kind", { ascending: true })
    .order("key", { ascending: true });
  if (error) return apiError(500, "server", "Could not load flags.");
  const list = (data ?? []) as Omit<FeatureFlagRow, "updated_by_email">[];
  const emails = await emailsFor(ctx.admin, list.flatMap((f) => (f.updated_by ? [f.updated_by] : []))).catch(() => new Map<string, string>());
  const flags: FeatureFlagRow[] = list.map((f) => ({
    ...f,
    value: f.value === null ? null : Number(f.value),
    allowlist: f.allowlist ?? [],
    updated_by_email: (f.updated_by && emails.get(f.updated_by)) || null,
  }));
  return json({ flags });
}
