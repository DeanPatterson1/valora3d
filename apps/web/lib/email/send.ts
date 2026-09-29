import type { EmailCategory } from "./categories";
import { SUPPORT_EMAIL } from "./categories";
import { unsubscribeHeaders, type UnsubscribeLinks } from "./unsubscribe";

/**
 * The one Resend send (https://resend.com/docs/api-reference/emails/send-email) for user-facing mail: HTML + plain
 * text, Reply-To support@, the category as a tag, List-Unsubscribe headers for opt-out categories, and an idempotency
 * key (Resend dedupes a retried send with the same key for 24 hours).
 */
export type OutgoingEmail = {
  to: string;
  subject: string;
  html: string;
  text: string;
  category: EmailCategory;
  /** Required for tips / renders; never set for account mail. */
  unsubscribe?: UnsubscribeLinks;
  idempotencyKey: string;
};

export type ResendAccount = { resendApiKey: string; from: string };

export function resendBody(from: string, mail: OutgoingEmail): Record<string, unknown> {
  return {
    from,
    to: [mail.to],
    subject: mail.subject,
    html: mail.html,
    text: mail.text,
    reply_to: SUPPORT_EMAIL,
    ...(mail.unsubscribe ? { headers: unsubscribeHeaders(mail.unsubscribe) } : {}),
    tags: [{ name: "category", value: mail.category }],
  };
}

export async function sendEmail(account: ResendAccount, mail: OutgoingEmail, fetchImpl: typeof fetch = (...a) => fetch(...a)): Promise<void> {
  if (mail.category !== "account" && !mail.unsubscribe) throw new Error("opt-out mail needs an unsubscribe link");
  const res = await fetchImpl("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${account.resendApiKey}`,
      "Content-Type": "application/json",
      "Idempotency-Key": mail.idempotencyKey.slice(0, 256),
    },
    body: JSON.stringify(resendBody(account.from, mail)),
  });
  if (!res.ok) throw new Error(`Resend failed: ${res.status}`);
}
