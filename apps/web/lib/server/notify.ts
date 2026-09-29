import type { EmailConfig } from "@/lib/env";
import { emailHtml, escapeHtml, raw } from "@/lib/email/layout";
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
};

/** Where the mail's "turn these off" line points (Settings, Notifications section). */
export const NOTIFICATION_SETTINGS_PATH = "/settings?section=notifications";

export function renderReadyEmail(ctx: RenderMailContext, siteUrl = SITE_URL): { subject: string; html: string; text: string } {
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
      `You're receiving this because a render finished on your Valora3D account. <a class="v-link" href="${escapeHtml(settings)}" style="color:#6b6b6b;text-decoration:underline;">Turn off render emails</a>.`,
    ),
  });
  return { subject: "Your render is ready", html, text };
}

/** Resend (https://resend.com/docs/api-reference/emails/send-email). The mail context lookup is injected. */
export class ResendNotifier implements RenderNotifier {
  constructor(
    private readonly config: EmailConfig,
    private readonly lookup: (userId: string, jobId: string) => Promise<RenderMailContext | null>,
    private readonly fetchImpl: typeof fetch = (...args) => fetch(...args),
  ) {}

  async notifyRenderReady(userId: string, jobId: string): Promise<void> {
    const ctx = await this.lookup(userId, jobId);
    // Opted out in Settings: send nothing (the job is still marked notified, so it is never retried).
    if (!ctx?.email || ctx.emailRenderReady === false) return;
    const mail = renderReadyEmail(ctx);
    const res = await this.fetchImpl("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.config.resendApiKey}`,
        "Content-Type": "application/json",
        // Resend dedupes a retried send with the same key for 24 h.
        "Idempotency-Key": `render-ready-${jobId}`,
      },
      body: JSON.stringify({ from: this.config.from, to: [ctx.email], subject: mail.subject, html: mail.html, text: mail.text }),
    });
    if (!res.ok) throw new Error(`Resend failed: ${res.status}`);
  }
}
