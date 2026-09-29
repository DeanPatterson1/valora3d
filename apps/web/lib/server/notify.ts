import type { EmailConfig } from "@/lib/env";
import { emailHtml, escapeHtml, raw } from "@/lib/email/layout";
import { sendEmail } from "@/lib/email/send";
import { unsubscribeLinks, type UnsubscribeLinks } from "@/lib/email/unsubscribe";
import { SITE_URL } from "@/lib/site";

/** "Your render is ready" mail. Best-effort: a failed send never fails the job transition that triggered it. */
export interface RenderNotifier {
  notifyRenderReady(userId: string, jobId: string): Promise<void>;
}

export const noopNotifier: RenderNotifier = { notifyRenderReady: async () => {} };

export type RenderMailContext = {
  email: string;
  name: string;
  projectId: string;
  projectName: string;
  /** profiles.email_render_ready: false = the user turned these mails off in Settings. Absent = on. */
  emailRenderReady?: boolean;
  /** A presigned poster link (lives up to 7 days, the SigV4 maximum), or none. */
  posterUrl?: string | null;
  /** Final or preview, for the wording. */
  kind?: "preview" | "final";
  /** The address hard-bounced or complained (email_suppressions): send nothing. */
  suppressed?: boolean;
};

/** Where the mail's "turn these off" line points (Settings, Notifications section). */
export const NOTIFICATION_SETTINGS_PATH = "/settings?section=notifications";

export function renderReadyEmail(ctx: RenderMailContext, siteUrl = SITE_URL, unsubscribe?: UnsubscribeLinks): { subject: string; html: string; text: string } {
  const link = `${siteUrl}/projects/${encodeURIComponent(ctx.projectId)}`;
  const settings = `${siteUrl}${NOTIFICATION_SETTINGS_PATH}`;
  const hello = ctx.name ? `Hi ${ctx.name},` : "Hi,";
  const what = ctx.kind === "preview" ? "preview render" : "render";
  const text = [
    hello,
    "",
    `Your ${what} of "${ctx.projectName}" is ready.`,
    "",
    `View it: ${link}`,
    "",
    "Renders are kept for your plan's retention period, so download the ones you want to keep.",
    "",
    `Don't want these emails? Turn them off in Settings: ${settings}`,
    ...(unsubscribe ? [`Or unsubscribe from render notifications in one click: ${unsubscribe.page}`] : []),
    "",
    "Valora3D",
  ].join("\n");
  const html = emailHtml({
    title: "Your render is ready",
    preheader: `${ctx.projectName} is ready to watch and download.`,
    image: ctx.posterUrl ? { src: ctx.posterUrl, alt: `Still from your render of ${ctx.projectName}`, href: link } : undefined,
    intro: [hello, raw(`Your ${what} of <strong>${escapeHtml(ctx.projectName)}</strong> is ready.`)],
    action: { label: "View render", href: escapeHtml(link) },
    outro: ["Renders are kept for your plan's retention period, so download the ones you want to keep."],
    footer: raw(
      `You're receiving this because a render finished on your Valora3D account. <a class="v-link" href="${escapeHtml(settings)}" style="color:#6b6b6b;text-decoration:underline;">Turn off render emails</a>${unsubscribe ? ` · <a class="v-link" href="${escapeHtml(unsubscribe.page)}" style="color:#6b6b6b;text-decoration:underline;">Unsubscribe</a>` : ""}.`,
    ),
  });
  return { subject: "Your render is ready", html, text };
}

/**
 * Resend (https://resend.com/docs/api-reference/emails/send-email) via lib/email/send.ts: Reply-To support@, and the
 * one-click List-Unsubscribe headers for render notifications. The mail context lookup is injected.
 */
export class ResendNotifier implements RenderNotifier {
  constructor(
    private readonly config: EmailConfig,
    private readonly lookup: (userId: string, jobId: string) => Promise<RenderMailContext | null>,
    /** lib/env.ts unsubscribeSecret (signs the one-click unsubscribe link). */
    private readonly unsubscribeSecret: string,
    private readonly fetchImpl: typeof fetch = (...args) => fetch(...args),
  ) {}

  async notifyRenderReady(userId: string, jobId: string): Promise<void> {
    const ctx = await this.lookup(userId, jobId);
    // Opted out in Settings, or the address bounced / complained: send nothing (the job is still marked notified,
    // so it is never retried).
    if (!ctx?.email || ctx.emailRenderReady === false || ctx.suppressed) return;
    const unsubscribe = await unsubscribeLinks(this.unsubscribeSecret, userId, "renders");
    const mail = renderReadyEmail(ctx, SITE_URL, unsubscribe);
    await sendEmail(
      this.config,
      { to: ctx.email, ...mail, category: "renders", unsubscribe, idempotencyKey: `render-ready-${jobId}` },
      this.fetchImpl,
    );
  }
}
