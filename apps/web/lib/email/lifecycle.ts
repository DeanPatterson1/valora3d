import { FREE_PLAN_CREDITS, PLAN_LIMITS, type PlanId } from "@/lib/pricing";
import { SITE_URL } from "@/lib/site";
import { CATEGORY_LABEL, SUPPORT_EMAIL, type OptOutCategory } from "./categories";
import { emailHtml, escapeHtml, raw, type Html } from "./layout";

/**
 * Lifecycle and billing mail, in the one Valora3D layout (lib/email/layout.ts). Every mail has an HTML and a
 * plain-text part with the same words; every link is also printed as text. Pure: the runner
 * (lib/server/lifecycle.ts) decides who gets what and when.
 */

export type Mail = { subject: string; html: string; text: string };

export type MailInput = {
  name: string;
  siteUrl?: string;
  /** The body link for opt-out mail (the /unsubscribe page). Required for tips and renders mail. */
  unsubscribePage?: string;
};

export type ExpiryInput = MailInput & { count: number; firstExpiry: Date; retentionDays: number; plan: PlanId };
export type BillingInput = MailInput & { plan: PlanId; at: Date | null; resumeAt?: Date | null };

const PLAN_NAME: Record<PlanId, string> = { free: "Free", creator: "Creator", pro: "Pro" };
const DATE: Intl.DateTimeFormatOptions = { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" };
export const fmtMailDate = (d: Date) => d.toLocaleDateString("en-US", DATE);

type Parts = {
  subject: string;
  title: string;
  preheader: string;
  intro: string[];
  steps?: string[];
  action?: { label: string; path: string };
  outro?: string[];
  /** Opt-out mail names its category; account mail says why it cannot be turned off. */
  category: OptOutCategory | "account";
};

function hello(name: string) {
  const n = name.trim();
  return n ? `Hi ${n},` : "Hi,";
}

/** Builds both parts from one description, so the HTML and the text never drift apart. */
function build(p: Parts, input: MailInput): Mail {
  const site = input.siteUrl ?? SITE_URL;
  const settings = `${site}/settings?section=notifications`;
  const href = p.action ? `${site}${p.action.path}` : null;
  const help = `${site}/help`;

  let footerText: string;
  let footerHtml: Html;
  if (p.category === "account") {
    footerText = "This is an account email about your Valora3D plan or billing, so it is sent even if you turn off other emails.";
    footerHtml = raw(escapeHtml(footerText));
  } else {
    if (!input.unsubscribePage) throw new Error("opt-out mail needs an unsubscribe link");
    const label = CATEGORY_LABEL[p.category];
    footerText = `You're receiving ${label} because you have a Valora3D account. Unsubscribe from ${label}: ${input.unsubscribePage} · Email settings: ${settings}`;
    footerHtml = raw(
      `You're receiving ${escapeHtml(label)} because you have a Valora3D account. <a class="v-link" href="${escapeHtml(input.unsubscribePage)}" style="color:#6b6b6b;text-decoration:underline;">Unsubscribe from ${escapeHtml(label)}</a> · <a class="v-link" href="${escapeHtml(settings)}" style="color:#6b6b6b;text-decoration:underline;">Email settings</a>`,
    );
  }

  const outro = [...(p.outro ?? []), `Questions? Reply to this email or write to ${SUPPORT_EMAIL}. Help center: ${help}`];
  const text = [
    hello(input.name),
    "",
    ...p.intro.flatMap((t) => [t, ""]),
    ...(p.steps ?? []).map((s, i) => `${i + 1}. ${s}`),
    ...(p.steps?.length ? [""] : []),
    ...(href && p.action ? [`${p.action.label}: ${href}`, ""] : []),
    ...outro.flatMap((t) => [t, ""]),
    "Valora3D",
    "",
    "--",
    footerText,
  ].join("\n");

  const html = emailHtml({
    title: p.title,
    preheader: p.preheader,
    intro: [hello(input.name), ...p.intro],
    steps: p.steps,
    action: href && p.action ? { label: p.action.label, href: escapeHtml(href) } : undefined,
    outro: [
      ...(p.outro ?? []),
      raw(
        `Questions? Reply to this email or write to <a class="v-link" href="mailto:${SUPPORT_EMAIL}" style="color:#6b6b6b;text-decoration:underline;">${SUPPORT_EMAIL}</a>. <a class="v-link" href="${escapeHtml(help)}" style="color:#6b6b6b;text-decoration:underline;">Help center</a>`,
      ),
    ],
    footer: footerHtml,
  });
  return { subject: p.subject, html, text };
}

export function welcomeEmail(input: MailInput): Mail {
  return build(
    {
      category: "tips",
      subject: "Welcome to Valora3D",
      title: "Welcome to Valora3D",
      preheader: "Your first video is three steps away.",
      intro: [`Your account is ready, with ${FREE_PLAN_CREDITS} free credits. Here's the quickest way to your first video:`],
      steps: [
        "Start a project and upload a .glb model, or pick one of the free sample models (a toy car, a camera or a watch).",
        "Describe the shot in one sentence, for example \"slow orbit at golden hour, low angle\".",
        "Render a preview. It's the cheapest render, so it's the right place to try ideas.",
      ],
      action: { label: "Start your first project", path: "/projects?new=1" },
      outro: ["Only have a .fbx, .obj or .blend file? The help center shows how to export a .glb in a few clicks."],
    },
    input,
  );
}

export function activationNudgeEmail(input: MailInput): Mail {
  return build(
    {
      category: "tips",
      subject: "Your first render is one sentence away",
      title: "Haven't rendered yet?",
      preheader: "No model handy? Start from a free sample.",
      intro: [
        "You signed up a couple of days ago but haven't made a video yet. That's fine: the first one takes about a minute of your time.",
        "No model at hand? Open a new project and pick a sample model. Then describe the shot and render a preview.",
      ],
      action: { label: "Try a sample model", path: "/projects?new=1" },
      outro: ["If something got in the way, reply and tell us. We read every message."],
    },
    input,
  );
}

export function tipsEmail(input: MailInput): Mail {
  return build(
    {
      category: "tips",
      subject: "Four tips for better renders",
      title: "Four tips for better renders",
      preheader: "Camera moves, framing, previews and share links.",
      intro: ["You've made your first renders. A few things that make the next ones better:"],
      steps: [
        "Name the camera move: \"slow push in\", \"orbit left\", \"crane up\". One move per shot reads best.",
        "Pick the format for where it will play: 9:16 for Reels and Shorts, 16:9 for sites and YouTube.",
        "Iterate on previews, then render the final once you like the shot.",
        "Share a render with a public link from the render's Share button. You can stop sharing any time.",
      ],
      action: { label: "Open your projects", path: "/projects" },
    },
    input,
  );
}

export function winbackEmail(input: MailInput): Mail {
  return build(
    {
      category: "tips",
      subject: "Your projects are still here",
      title: "Pick up where you left off",
      preheader: "Your projects and scenes are saved.",
      intro: [
        "It's been a while since you used Valora3D. Your projects and scenes are saved, so you can pick up where you left off.",
        "Uploaded models are kept for your plan's retention period after their last use; if one has expired, upload it again.",
      ],
      action: { label: "Open your projects", path: "/projects" },
      outro: ["Not for you? Reply and tell us why. It helps more than you'd think."],
    },
    input,
  );
}

export function expiryWarningEmail(input: ExpiryInput): Mail {
  const when = fmtMailDate(input.firstExpiry);
  const what = input.count === 1 ? "A render" : `${input.count} renders`;
  const paid = (["creator", "pro"] as const).map((p) => `${PLAN_NAME[p]} keeps them ${PLAN_LIMITS[p].retentionDays} days`).join(", ");
  return build(
    {
      category: "renders",
      subject: `${what} will be deleted on ${when}`,
      title: `${what} will be deleted soon`,
      preheader: `Download before ${when} to keep ${input.count === 1 ? "it" : "them"}.`,
      intro: [
        `Renders are kept for ${input.retentionDays} days on your plan. ${input.count === 1 ? "One of your renders" : `${input.count} of your renders`} will be deleted on or after ${when}.`,
        `Download ${input.count === 1 ? "it" : "the ones you want to keep"} before then. Deleted renders can't be recovered.`,
      ],
      action: { label: "Download your renders", path: "/profile?tab=billing" },
      outro: input.plan === "free" ? [`Want longer? ${paid}.`] : [],
    },
    input,
  );
}

export function pastDueEmail(input: BillingInput): Mail {
  const plan = PLAN_NAME[input.plan];
  return build(
    {
      category: "account",
      subject: "Your payment didn't go through",
      title: "Your payment didn't go through",
      preheader: `Update your payment method to keep ${plan}.`,
      intro: [
        `We couldn't charge your payment method for your ${plan} plan. Our payment provider, Paddle, will retry it automatically over the next few days.`,
        `To keep ${plan} without a gap, update your payment method now. Until the retries run out, your plan keeps working.`,
      ],
      action: { label: "Update payment method", path: "/profile?tab=billing&payment=update" },
    },
    input,
  );
}

export function planCanceledEmail(input: BillingInput): Mail {
  const plan = PLAN_NAME[input.plan];
  return build(
    {
      category: "account",
      subject: `Your ${plan} plan has ended`,
      title: `Your ${plan} plan has ended`,
      preheader: "Your account is now on Free. Your credits stay.",
      intro: [
        `Your ${plan} subscription has ended and your account is now on Free. Nothing more will be charged.`,
        "Your remaining credits stay on your account, and renders you already made keep their original expiry dates.",
      ],
      action: { label: "See plans", path: "/pricing" },
      outro: ["If you canceled by mistake, you can subscribe again at any time."],
    },
    input,
  );
}

export function cancelScheduledEmail(input: BillingInput): Mail {
  const plan = PLAN_NAME[input.plan];
  const until = input.at ? fmtMailDate(input.at) : "the end of your billing period";
  return build(
    {
      category: "account",
      subject: `Your ${plan} plan will end on ${until}`,
      title: "Your cancellation is confirmed",
      preheader: `You keep ${plan} until ${until}.`,
      intro: [
        `Your ${plan} plan is set to end on ${until}. You keep everything in ${plan} until then, and nothing more will be charged.`,
        "Changed your mind? Reply to this email before that date and we'll keep your plan running.",
      ],
      action: { label: "Usage & billing", path: "/profile?tab=billing" },
    },
    input,
  );
}

export function planPausedEmail(input: BillingInput): Mail {
  const plan = PLAN_NAME[input.plan];
  const from = input.at ? fmtMailDate(input.at) : "the end of your billing period";
  const resume = input.resumeAt ? fmtMailDate(input.resumeAt) : null;
  return build(
    {
      category: "account",
      subject: `Your ${plan} plan will pause on ${from}`,
      title: "Your pause is scheduled",
      preheader: resume ? `Billing resumes on ${resume}.` : "No charges while it's paused.",
      intro: [
        `Your ${plan} plan will pause on ${from}. You keep ${plan} until then, and you won't be charged while it's paused.`,
        resume
          ? `It resumes on ${resume} and bills as usual from then. Your credits and projects stay on your account.`
          : "Your credits and projects stay on your account while it's paused.",
      ],
      action: { label: "Usage & billing", path: "/profile?tab=billing" },
    },
    input,
  );
}

