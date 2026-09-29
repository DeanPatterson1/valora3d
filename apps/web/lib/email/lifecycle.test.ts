import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { CANCEL_REASONS } from "@/lib/billing/cancel";
import { kindCategory, LIFECYCLE_KINDS } from "./categories";
import {
  activationNudgeEmail,
  cancelScheduledEmail,
  expiryWarningEmail,
  pastDueEmail,
  planCanceledEmail,
  planPausedEmail,
  tipsEmail,
  welcomeEmail,
  winbackEmail,
} from "./lifecycle";
import { resendBody, sendEmail } from "./send";
import { unsubscribeHeaders, unsubscribeLinks, unsubscribeToken, verifyUnsubscribeToken } from "./unsubscribe";

const SQL = readFileSync(join(import.meta.dirname, "../../supabase/migrations/20260930130000_lifecycle.sql"), "utf8");
const SITE = "https://valora3d.com";
const UNSUB = "https://valora3d.com/unsubscribe?u=x&c=tips&t=y";
const USER = "3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f";

describe("kinds and categories match the database", () => {
  it("email_kinds() lists exactly LIFECYCLE_KINDS", () => {
    const list = SQL.match(/function public\.email_kinds\(\)[\s\S]*?array\[([\s\S]*?)\]::text\[\]/)?.[1] ?? "";
    expect([...list.matchAll(/'([a-z_]+)'/g)].map((m) => m[1])).toEqual([...LIFECYCLE_KINDS]);
  });
  it("email_kind_category() agrees with kindCategory()", () => {
    const tips = SQL.match(/when p_kind in \(([^)]*)\) then 'tips'/)?.[1] ?? "";
    const tipKinds = [...tips.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]);
    for (const k of LIFECYCLE_KINDS) {
      const want = tipKinds.includes(k) ? "tips" : k === "expiry_warning" ? "renders" : "account";
      expect(kindCategory(k), k).toBe(want);
    }
  });
  it("cancellation reasons match the table check", () => {
    const table = SQL.slice(SQL.indexOf("create table public.cancellation_feedback"));
    const check = table.match(/reason\s+text not null check \(reason in\s*\(([^)]*)\)\)/)?.[1] ?? "";
    expect([...check.matchAll(/'([a-z_]+)'/g)].map((m) => m[1])).toEqual(CANCEL_REASONS.map((r) => r.id));
  });
});

describe("lifecycle templates", () => {
  const optOut = [
    ["welcome", welcomeEmail({ name: "Ada <b>", siteUrl: SITE, unsubscribePage: UNSUB })],
    ["nudge", activationNudgeEmail({ name: "Ada", siteUrl: SITE, unsubscribePage: UNSUB })],
    ["tips", tipsEmail({ name: "Ada", siteUrl: SITE, unsubscribePage: UNSUB })],
    ["winback", winbackEmail({ name: "", siteUrl: SITE, unsubscribePage: UNSUB })],
    [
      "expiry",
      expiryWarningEmail({ name: "Ada", siteUrl: SITE, unsubscribePage: UNSUB, count: 3, firstExpiry: new Date("2026-10-04T10:00:00Z"), retentionDays: 7, plan: "free" }),
    ],
  ] as const;
  const account = [
    ["past_due", pastDueEmail({ name: "Ada", siteUrl: SITE, plan: "creator", at: null })],
    ["canceled", planCanceledEmail({ name: "Ada", siteUrl: SITE, plan: "pro", at: null })],
    ["scheduled", cancelScheduledEmail({ name: "Ada", siteUrl: SITE, plan: "pro", at: new Date("2026-10-28T00:00:00Z") })],
    ["paused", planPausedEmail({ name: "Ada", siteUrl: SITE, plan: "creator", at: new Date("2026-10-28T00:00:00Z"), resumeAt: new Date("2026-11-27T00:00:00Z") })],
  ] as const;

  it.each(optOut)("%s: both parts, a button link, an unsubscribe link, the support line", (_, mail) => {
    expect(mail.html).toContain(`href="${UNSUB.replace(/&/g, "&amp;")}"`);
    expect(mail.text).toContain(UNSUB);
    expect(mail.html).toContain("support@valora3d.com");
    expect(mail.text).toContain("Reply to this email");
    expect(mail.html).toMatch(/class="v-btn-a" href="https:\/\/valora3d\.com\//);
    expect(mail.text).not.toMatch(/<(strong|a|p|table)\b/);
  });

  it.each(account)("%s: transactional, no unsubscribe link, says why", (_, mail) => {
    expect(mail.html).not.toContain("/unsubscribe");
    expect(mail.text).toContain("sent even if you turn off other emails");
    expect(mail.html).toMatch(/class="v-btn-a" href="https:\/\/valora3d\.com\//);
  });

  it("escapes the name and says hi without one", () => {
    const [, welcome] = optOut[0];
    expect(welcome.html).toContain("Hi Ada &lt;b&gt;,");
    expect(welcome.html).not.toContain("Ada <b>");
    expect(optOut[3][1].text.startsWith("Hi,\n")).toBe(true);
  });

  it("the expiry warning names the count and date, and upsells only on Free", () => {
    const [, free] = optOut[4];
    expect(free.subject).toBe("3 renders will be deleted on October 4, 2026");
    expect(free.text).toContain("Creator keeps them 30 days");
    const paid = expiryWarningEmail({ name: "A", unsubscribePage: UNSUB, count: 1, firstExpiry: new Date("2026-10-04T00:00:00Z"), retentionDays: 30, plan: "creator" });
    expect(paid.subject).toBe("A render will be deleted on October 4, 2026");
    expect(paid.text).not.toContain("keeps them");
  });

  it("refuses to build opt-out mail without an unsubscribe link", () => {
    expect(() => welcomeEmail({ name: "A" })).toThrow(/unsubscribe/);
  });

  it("the past-due mail links to the payment update", () => {
    expect(account[0][1].text).toContain("https://valora3d.com/profile?tab=billing&payment=update");
  });

  // EMAIL_PREVIEW_DIR=<dir> npx vitest run lib/email/lifecycle.test.ts writes every mail as an .html file to look at.
  it("writes previews on request", () => {
    const dir = process.env.EMAIL_PREVIEW_DIR;
    if (!dir) return;
    mkdirSync(dir, { recursive: true });
    for (const [name, mail] of [...optOut, ...account]) writeFileSync(join(dir, `${name}.html`), mail.html);
  });
});

describe("one-click unsubscribe tokens", () => {
  it("verify for the same user and category only", async () => {
    const t = await unsubscribeToken("secret-1", USER, "tips");
    expect(t).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(await verifyUnsubscribeToken("secret-1", USER, "tips", t)).toBe(true);
    expect(await verifyUnsubscribeToken("secret-1", USER.toUpperCase(), "tips", t)).toBe(true);
    expect(await verifyUnsubscribeToken("secret-1", USER, "renders", t)).toBe(false);
    expect(await verifyUnsubscribeToken("secret-2", USER, "tips", t)).toBe(false);
    expect(await verifyUnsubscribeToken("secret-1", "7a1d2e3f-4b5c-4d6e-8f90-a1b2c3d4e5f6", "tips", t)).toBe(false);
    expect(await verifyUnsubscribeToken("secret-1", USER, "account", t)).toBe(false);
    expect(await verifyUnsubscribeToken("secret-1", USER, "tips", `${t.slice(0, -1)}A`)).toBe(t.endsWith("A"));
  });

  it("builds the RFC 8058 headers and the page link", async () => {
    const links = await unsubscribeLinks("s", USER, "renders", SITE);
    expect(links.oneClick).toMatch(/^https:\/\/valora3d\.com\/api\/email\/unsubscribe\?u=.+&c=renders&t=/);
    expect(links.page).toMatch(/^https:\/\/valora3d\.com\/unsubscribe\?/);
    expect(unsubscribeHeaders(links)).toEqual({
      "List-Unsubscribe": `<${links.oneClick}>`,
      "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    });
  });
});

describe("sendEmail", () => {
  it("sends Reply-To support, the unsubscribe headers, a category tag and an idempotency key", async () => {
    const links = await unsubscribeLinks("s", USER, "tips", SITE);
    const calls: [string, RequestInit][] = [];
    const fetchImpl = (async (url: string, init: RequestInit) => {
      calls.push([url, init]);
      return Response.json({ id: "m" });
    }) as unknown as typeof fetch;
    await sendEmail({ resendApiKey: "re_1", from: "Valora3D <hello@valora3d.com>" }, { to: "a@b.co", subject: "S", html: "<p>h</p>", text: "t", category: "tips", unsubscribe: links, idempotencyKey: "welcome:u:once" }, fetchImpl);
    const [url, init] = calls[0];
    expect(url).toBe("https://api.resend.com/emails");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("welcome:u:once");
    const body = JSON.parse(String(init.body));
    expect(body).toMatchObject({ reply_to: "support@valora3d.com", to: ["a@b.co"], tags: [{ name: "category", value: "tips" }] });
    expect(body.headers["List-Unsubscribe-Post"]).toBe("List-Unsubscribe=One-Click");
  });

  it("account mail carries no unsubscribe headers; opt-out mail without a link is refused", async () => {
    expect(resendBody("f", { to: "a@b.co", subject: "S", html: "h", text: "t", category: "account", idempotencyKey: "k" })).not.toHaveProperty("headers");
    await expect(sendEmail({ resendApiKey: "k", from: "f" }, { to: "a@b.co", subject: "S", html: "h", text: "t", category: "renders", idempotencyKey: "k" })).rejects.toThrow();
  });
});
