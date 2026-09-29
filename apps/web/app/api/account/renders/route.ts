import { z } from "@/lib/zod";
import { pageRange, toPage, type AccountRender } from "@/lib/account/history";
import type { RenderJobRow } from "@/lib/render/jobRow";
import { toClientJob } from "@/lib/server/renderContext";
import { apiError, requireUser } from "@/lib/supabase/server";

const PageParam = z.coerce.number().int().min(0).max(10_000);

type Row = RenderJobRow & { projects: { name: string } | null };

/**
 * GET /api/account/renders?page=N — the caller's renders across every project, newest first, 20 a page.
 * Read with the user's own client (RLS: own rows only); poster and video links are short-lived presigned GETs.
 */
export async function GET(request: Request) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const page = PageParam.safeParse(new URL(request.url).searchParams.get("page") ?? "0");
  if (!page.success) return apiError(400, "invalid_request", "page must be a whole number.");
  const { from, to } = pageRange(page.data);
  const { data, error } = await ctx.userClient
    .from("render_jobs")
    .select("*, projects(name)")
    .order("created_at", { ascending: false })
    .range(from, to);
  if (error) return apiError(500, "server", "Could not load renders.");
  const items: AccountRender[] = await Promise.all(
    ((data ?? []) as Row[]).map(async ({ projects, ...row }) => ({
      job: await toClientJob(ctx.config, row),
      projectName: projects?.name ?? "Deleted project",
    })),
  );
  return Response.json(toPage(items, page.data), { headers: { "Cache-Control": "no-store" } });
}
