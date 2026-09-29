import { z } from "zod";
import { routeTemplate } from "@/lib/analytics/events";

/**
 * In-app feedback (the sidebar "Feedback" item, the help center and error pages' "Report this problem"). Shared by the
 * dialog and POST /api/feedback; mirrors the checks on public.feedback (20260930130000_lifecycle.sql).
 * The page is reduced to a route template and the browser to a family, so a report carries no ids or URLs beyond
 * what the person typed.
 */

export const FEEDBACK_KINDS = [
  { id: "bug", label: "Bug", hint: "Something broke or behaved wrongly." },
  { id: "idea", label: "Idea", hint: "Something you'd like Valora3D to do." },
  { id: "question", label: "Question", hint: "Something you'd like to know." },
] as const;
export type FeedbackKind = (typeof FEEDBACK_KINDS)[number]["id"];
export const FEEDBACK_STATUSES = ["new", "triaged", "done"] as const;
export type FeedbackStatus = (typeof FEEDBACK_STATUSES)[number];

export const MESSAGE_MIN = 3;
export const MESSAGE_MAX = 4000;

export const FeedbackRequest = z
  .object({
    kind: z.enum(FEEDBACK_KINDS.map((k) => k.id) as [FeedbackKind, ...FeedbackKind[]]),
    message: z.string().trim().min(MESSAGE_MIN).max(MESSAGE_MAX),
    page: z.string().max(300).optional(),
    release: z.string().max(60).optional(),
  })
  .strict();

const RELEASE = /^[A-Za-z0-9._-]{1,40}$/;

/** The row the route inserts (with the browser family it adds from the User-Agent header). */
export function feedbackRow(body: z.infer<typeof FeedbackRequest>, uaFamily: string) {
  return {
    kind: body.kind,
    message: body.message,
    page: body.page ? routeTemplate(body.page) : null,
    release: body.release && RELEASE.test(body.release) ? body.release : null,
    ua_family: /^[a-z_]{1,24}$/.test(uaFamily) ? uaFamily : null,
  };
}

/** An `?feedback=` / `?from=` pair from an error page: which kind to preselect, which page it came from. */
export function feedbackIntent(params: { get(name: string): string | null }): { kind: FeedbackKind; from: string | null } | null {
  const k = params.get("feedback");
  if (!k) return null;
  const kind = (FEEDBACK_KINDS.some((x) => x.id === k) ? k : "bug") as FeedbackKind;
  const from = params.get("from");
  return { kind, from: from && from.startsWith("/") ? routeTemplate(from) : null };
}
