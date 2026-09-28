import type { EmailConfig } from "@/lib/env";
import { SITE_URL } from "@/lib/site";

/** "Your render is ready" mail. Best-effort: a failed send never fails the job transition that triggered it. */
export interface RenderNotifier {
  notifyRenderReady(userId: string, jobId: string): Promise<void>;
}

export const noopNotifier: RenderNotifier = { notifyRenderReady: async () => {} };

export type RenderMailContext = { email: string; name: string; projectId: string; projectName: string };

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

export function renderReadyEmail(ctx: RenderMailContext, siteUrl = SITE_URL): { subject: string; html: string; text: string } {
  const link = `${siteUrl}/projects/${encodeURIComponent(ctx.projectId)}`;
  const hello = ctx.name ? `Hi ${ctx.name},` : "Hi,";
  const text = `${hello}\n\nYour render of "${ctx.projectName}" is ready.\n\nOpen it: ${link}\n\nValora3D`;
  const html = `<p>${escapeHtml(hello)}</p><p>Your render of <strong>${escapeHtml(ctx.projectName)}</strong> is ready.</p><p><a href="${escapeHtml(link)}">Open your project</a></p><p>Valora3D</p>`;
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
    if (!ctx?.email) return;
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
