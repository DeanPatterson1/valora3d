import { readBody, sameOrigin } from "@/lib/server/api";
import { createShare, getShare, revokeShare, ShareBodySchema, SupabaseShareStore } from "@/lib/server/shares";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

type Params = { params: Promise<{ id: string }> };

/** GET /api/renders/:id/share: the caller's live public link for their render, or `{ share: null }`. */
export async function GET(_request: Request, { params }: Params) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  return getShare(new SupabaseShareStore(createServiceSupabase(ctx.config), ctx.userClient), id);
}

/** POST /api/renders/:id/share `{ show_prompt }`: creates the public link (or updates it). Owner only, rate limited. */
export async function POST(request: Request, { params }: Params) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, ShareBodySchema);
  if (body instanceof Response) return body;
  const { id } = await params;
  return createShare(new SupabaseShareStore(createServiceSupabase(ctx.config), ctx.userClient), ctx.user.id, id, body);
}

/** DELETE /api/renders/:id/share: stops sharing; the old link answers 410 from then on. */
export async function DELETE(request: Request, { params }: Params) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  return revokeShare(new SupabaseShareStore(createServiceSupabase(ctx.config), ctx.userClient), ctx.user.id, id);
}
