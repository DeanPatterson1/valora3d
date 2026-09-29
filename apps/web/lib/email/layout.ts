/**
 * The one Valora3D email layout: the Supabase auth templates (supabase/templates/*.html, generated from
 * lib/email/authTemplates.ts) and the render-ready mail (lib/server/notify.ts) all come from here.
 *
 * Rules for mail clients: tables for layout, inline styles on every element (Gmail drops most <style>),
 * no web fonts or external images, a light default with a prefers-color-scheme dark override for the
 * clients that honour it (Apple Mail, iOS, Outlook.com); clients that force their own dark mode (Gmail app,
 * Outlook) invert a plain black/white design cleanly. Every link is also printed as text, so a client that
 * blocks the button still shows a usable URL.
 */

export const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

/** A piece of HTML that is already safe to insert as-is. */
export type Html = { __html: string };
export const raw = (html: string): Html => ({ __html: html });
const out = (v: string | Html) => (typeof v === "string" ? escapeHtml(v) : v.__html);

const FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,Helvetica,Arial,sans-serif";

export type EmailLayout = {
  /** <title> and the heading. */
  title: string;
  /** Hidden preview line shown next to the subject in the inbox. */
  preheader: string;
  /** Paragraphs above the button. */
  intro: (string | Html)[];
  /** Numbered steps between the intro and the button (lifecycle mail). */
  steps?: (string | Html)[];
  /** The one action. `href` is inserted verbatim (may carry Supabase template variables), so pass only trusted URLs. */
  action?: { label: string; href: string };
  /** An optional image above the text (the render poster). Only ever a URL we minted. */
  image?: { src: string; alt: string; href?: string };
  /** A one-time code shown large (reauthentication). */
  code?: string | Html;
  /** Paragraphs under the button, in smaller muted text. */
  outro?: (string | Html)[];
  /** Footer line (why they got this mail, how to stop it). */
  footer: string | Html;
};

/** Builds the full HTML document. */
export function emailHtml(l: EmailLayout): string {
  const p = (text: string | Html, muted = false) =>
    `<p class="v-${muted ? "muted" : "text"}" style="margin:0 0 16px;font-family:${FONT};font-size:${muted ? 13 : 15}px;line-height:1.6;color:${muted ? "#6b6b6b" : "#0d0d0d"};">${out(text)}</p>`;

  const image = l.image
    ? `<tr><td style="padding:0 32px 24px;">${l.image.href ? `<a href="${escapeHtml(l.image.href)}" style="text-decoration:none;">` : ""}<img src="${escapeHtml(l.image.src)}" alt="${escapeHtml(l.image.alt)}" width="496" style="display:block;width:100%;max-width:496px;height:auto;border:0;border-radius:12px;background-color:#e6e6e6;" />${l.image.href ? "</a>" : ""}</td></tr>`
    : "";

  const button = l.action
    ? `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 24px;"><tr><td class="v-btn" bgcolor="#0d0d0d" style="border-radius:999px;background-color:#0d0d0d;"><a class="v-btn-a" href="${l.action.href}" target="_blank" style="display:inline-block;padding:13px 28px;font-family:${FONT};font-size:15px;font-weight:600;line-height:1;color:#ffffff;text-decoration:none;border-radius:999px;">${escapeHtml(l.action.label)}</a></td></tr></table>`
    : "";

  const code = l.code
    ? `<p class="v-code" style="margin:8px 0 24px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:28px;letter-spacing:6px;font-weight:600;color:#0d0d0d;">${out(l.code)}</p>`
    : "";

  const steps = l.steps?.length
    ? `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px;">${l.steps
        .map(
          (s, i) =>
            `<tr><td valign="top" class="v-text" style="padding:0 12px 10px 0;font-family:${FONT};font-size:15px;line-height:1.6;font-weight:600;color:#0d0d0d;">${i + 1}.</td><td valign="top" class="v-text" style="padding:0 0 10px;font-family:${FONT};font-size:15px;line-height:1.6;color:#0d0d0d;">${out(s)}</td></tr>`,
        )
        .join("")}</table>`
    : "";

  const fallback = l.action
    ? p(raw(`If the button doesn't work, copy this link into your browser:<br /><a class="v-link" href="${l.action.href}" style="color:#0d0d0d;text-decoration:underline;word-break:break-all;">${l.action.href}</a>`), true)
    : "";

  return `<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="x-apple-disable-message-reformatting" />
<meta name="color-scheme" content="light dark" />
<meta name="supported-color-schemes" content="light dark" />
<title>${escapeHtml(l.title)}</title>
<style>
  :root { color-scheme: light dark; supported-color-schemes: light dark; }
  @media (prefers-color-scheme: dark) {
    .v-bg { background-color: #0d0d0d !important; }
    .v-card { background-color: #171717 !important; border-color: #2a2a2a !important; }
    .v-text, .v-title, .v-brand, .v-code { color: #ffffff !important; }
    .v-muted { color: #a3a3a3 !important; }
    .v-link { color: #ffffff !important; }
    .v-btn { background-color: #ffffff !important; }
    .v-btn-a { color: #0d0d0d !important; }
  }
  @media only screen and (max-width: 600px) {
    .v-card-pad { padding-left: 20px !important; padding-right: 20px !important; }
  }
</style>
</head>
<body class="v-bg" style="margin:0;padding:0;background-color:#f4f4f4;-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">${escapeHtml(l.preheader)}</div>
<table role="presentation" class="v-bg" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4f4f4" style="background-color:#f4f4f4;">
<tr><td align="center" style="padding:32px 12px;">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:560px;">
<tr><td style="padding:0 8px 20px;">
<!-- Optional logo: replace the wordmark below with a hosted image, e.g.
     <img src="https://valora3d.com/email/logo.png" alt="Valora3D" width="120" style="display:block;border:0;" /> -->
<span class="v-brand" style="font-family:${FONT};font-size:18px;font-weight:700;letter-spacing:-0.02em;color:#0d0d0d;">Valora3D</span>
</td></tr>
<tr><td class="v-card" bgcolor="#ffffff" style="background-color:#ffffff;border:1px solid #e6e6e6;border-radius:16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td class="v-card-pad" style="padding:32px 32px 8px;">
<h1 class="v-title" style="margin:0 0 16px;font-family:${FONT};font-size:22px;line-height:1.3;font-weight:600;letter-spacing:-0.02em;color:#0d0d0d;">${escapeHtml(l.title)}</h1>
</td></tr>
${image}<tr><td class="v-card-pad" style="padding:0 32px 16px;">
${l.intro.map((t) => p(t)).join("\n")}
${steps}${button}${code}${fallback}
${(l.outro ?? []).map((t) => p(t, true)).join("\n")}
</td></tr>
</table>
</td></tr>
<tr><td style="padding:20px 8px 0;">
<p class="v-muted" style="margin:0;font-family:${FONT};font-size:12px;line-height:1.6;color:#6b6b6b;">${out(l.footer)}</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
`;
}
