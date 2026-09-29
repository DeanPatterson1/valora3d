import { emailHtml, raw } from "./layout";

/**
 * Supabase Auth email templates, in the Valora3D layout. `supabase/templates/<file>` is generated from this
 * (lib/email/authTemplates.test.ts fails if they drift; `WRITE_EMAIL_TEMPLATES=1 npx vitest run lib/email`
 * rewrites them). `supabase/config.toml` points the local stack at the files; the hosted project needs the
 * same subject + HTML pasted into Authentication -> Email Templates (README, "Auth emails").
 *
 * Links use the token-hash flow (`/auth/confirm?token_hash=…&type=…`) rather than {{ .ConfirmationURL }}: it
 * works when the mail is opened on another device or browser than the one that asked for it (the PKCE code
 * link does not), and app/auth/confirm/route.ts verifies it server-side. Template variables are Go template
 * syntax filled in by Supabase Auth: {{ .SiteURL }}, {{ .TokenHash }}, {{ .Token }}, {{ .Email }}, {{ .NewEmail }}.
 */

export type AuthTemplate = {
  /** config.toml key: [auth.email.template.<key>] or [auth.email.notification.<key>]. */
  key: string;
  group: "template" | "notification";
  /** Dashboard name (Authentication -> Email Templates). */
  dashboard: string;
  file: string;
  subject: string;
  /** Supabase variables the HTML must contain (pinned by the test). */
  variables: string[];
  html: string;
};

const confirmLink = (type: string, next: string) =>
  `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=${type}&next=${next}`;

const NOT_YOU = "If you didn't ask for this, you can ignore this email. Nothing changes until the link is used.";
const FOOTER = "Valora3D · valora3d.com. You're receiving this because of an action on your Valora3D account.";
const SITE = "https://valora3d.com";

export const AUTH_TEMPLATES: AuthTemplate[] = [
  {
    key: "confirmation",
    group: "template",
    dashboard: "Confirm signup",
    file: "confirmation.html",
    subject: "Confirm your Valora3D email",
    // `next` is the address the signup asked to return to (lib/nav/next.ts: authCallbackUrl), so a plan chosen
    // before signup still opens its checkout after confirming. /auth/confirm keeps only its same-origin path.
    variables: ["{{ .SiteURL }}", "{{ .TokenHash }}", "{{ .Email }}", "{{ .RedirectTo }}"],
    html: emailHtml({
      title: "Confirm your email",
      preheader: "One click and your Valora3D account is ready.",
      intro: [raw("Confirm that <strong>{{ .Email }}</strong> is your address to finish creating your Valora3D account. Your free credits are added as soon as you confirm.")],
      action: { label: "Confirm email", href: confirmLink("email", "{{ .RedirectTo }}") },
      outro: ["This link works once and expires in 24 hours.", NOT_YOU],
      footer: FOOTER,
    }),
  },
  {
    key: "magic_link",
    group: "template",
    dashboard: "Magic link",
    file: "magic_link.html",
    subject: "Your Valora3D sign-in link",
    variables: ["{{ .SiteURL }}", "{{ .TokenHash }}"],
    html: emailHtml({
      title: "Sign in to Valora3D",
      preheader: "Your one-time sign-in link.",
      intro: ["Use this button to sign in. No password needed."],
      action: { label: "Sign in", href: confirmLink("email", "/projects") },
      outro: ["This link works once and expires soon.", "If you didn't try to sign in, you can ignore this email. Your account stays safe."],
      footer: FOOTER,
    }),
  },
  {
    key: "recovery",
    group: "template",
    dashboard: "Reset password",
    file: "recovery.html",
    subject: "Reset your Valora3D password",
    variables: ["{{ .SiteURL }}", "{{ .TokenHash }}", "{{ .Email }}"],
    html: emailHtml({
      title: "Reset your password",
      preheader: "Choose a new password for your Valora3D account.",
      intro: [raw("We got a request to reset the password for <strong>{{ .Email }}</strong>. Choose a new one here:")],
      action: { label: "Choose a new password", href: confirmLink("recovery", "/reset-password") },
      outro: ["This link works once and expires in 1 hour.", "If you didn't ask to reset your password, ignore this email. Your current password still works."],
      footer: FOOTER,
    }),
  },
  {
    key: "email_change",
    group: "template",
    dashboard: "Change email address",
    file: "email_change.html",
    subject: "Confirm your new Valora3D email",
    variables: ["{{ .SiteURL }}", "{{ .TokenHash }}", "{{ .Email }}", "{{ .NewEmail }}"],
    html: emailHtml({
      title: "Confirm your new email",
      preheader: "Confirm the change to your Valora3D sign-in email.",
      intro: [raw("Confirm changing your Valora3D email from <strong>{{ .Email }}</strong> to <strong>{{ .NewEmail }}</strong>.")],
      action: { label: "Confirm change", href: confirmLink("email_change", "/settings") },
      outro: [
        "For your security we send this to both addresses; the change happens once each is confirmed.",
        `If you didn't ask for this, don't click the link and reset your password at ${SITE}/forgot-password.`,
      ],
      footer: FOOTER,
    }),
  },
  {
    key: "invite",
    group: "template",
    dashboard: "Invite user",
    file: "invite.html",
    subject: "You're invited to Valora3D",
    variables: ["{{ .SiteURL }}", "{{ .TokenHash }}"],
    html: emailHtml({
      title: "You're invited to Valora3D",
      preheader: "Accept your invite and set a password.",
      intro: ["You've been invited to Valora3D: upload a 3D model, describe the shot, and get a video. Accept the invite to set your password."],
      action: { label: "Accept invite", href: confirmLink("invite", "/reset-password") },
      outro: ["This invite works once.", "If you weren't expecting it, you can ignore this email."],
      footer: FOOTER,
    }),
  },
  {
    key: "reauthentication",
    group: "template",
    dashboard: "Reauthentication",
    file: "reauthentication.html",
    subject: "Your Valora3D verification code",
    variables: ["{{ .Token }}"],
    html: emailHtml({
      title: "Confirm it's you",
      preheader: "Your Valora3D verification code.",
      intro: ["Enter this code to confirm a sensitive change to your account:"],
      code: raw("{{ .Token }}"),
      outro: ["The code expires soon.", "If you didn't ask for it, someone may know your password: reset it now."],
      footer: FOOTER,
    }),
  },
  {
    key: "password_changed",
    group: "notification",
    dashboard: "Security notifications: Password changed",
    file: "password_changed_notification.html",
    subject: "Your Valora3D password was changed",
    variables: [],
    html: emailHtml({
      title: "Your password was changed",
      preheader: "The password on your Valora3D account was just changed.",
      intro: ["The password for your Valora3D account was just changed. If that was you, there's nothing to do."],
      action: { label: "Reset password", href: `${SITE}/forgot-password` },
      outro: ["If you didn't change it, reset your password now and contact support."],
      footer: FOOTER,
    }),
  },
  {
    key: "email_changed",
    group: "notification",
    dashboard: "Security notifications: Email address changed",
    file: "email_changed_notification.html",
    subject: "Your Valora3D email was changed",
    variables: [],
    html: emailHtml({
      title: "Your email was changed",
      preheader: "The sign-in email on your Valora3D account was changed.",
      intro: ["The sign-in email for your Valora3D account was just changed. If that was you, there's nothing to do."],
      outro: [`If you didn't change it, contact support right away from ${SITE}/contact.`],
      footer: FOOTER,
    }),
  },
];
