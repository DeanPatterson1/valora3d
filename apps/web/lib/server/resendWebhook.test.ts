import { describe, expect, it } from "vitest";
import { readResendWebhookSecret, readServerConfig, readUnsubscribeSecret } from "@/lib/env";
import { suppressionsFrom, svixSignature, verifySvix } from "./resendWebhook";

// The Svix docs' example key format: whsec_ + base64.
const SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw";
const BODY = JSON.stringify({ type: "email.bounced", data: { to: ["Someone@Example.com"], bounce: { type: "Permanent" } } });

describe("Svix signature (Resend webhooks)", () => {
  it("accepts a correct v1 signature within five minutes, among several", async () => {
    const ts = "1790000000";
    const sig = await svixSignature(SECRET, "msg_1", ts, BODY);
    const h = { id: "msg_1", timestamp: ts, signature: `v1,bm9wZQ== v1,${sig}` };
    expect(await verifySvix(SECRET, h, BODY, 1790000000_000)).toBe(true);
    expect(await verifySvix(SECRET, h, BODY, (1790000000 + 299) * 1000)).toBe(true);
  });

  it("refuses a stale timestamp, a changed body, another id or a missing header", async () => {
    const ts = "1790000000";
    const sig = await svixSignature(SECRET, "msg_1", ts, BODY);
    const ok = { id: "msg_1", timestamp: ts, signature: `v1,${sig}` };
    expect(await verifySvix(SECRET, ok, BODY, (1790000000 + 301) * 1000)).toBe(false);
    expect(await verifySvix(SECRET, ok, `${BODY} `, 1790000000_000)).toBe(false);
    expect(await verifySvix(SECRET, { ...ok, id: "msg_2" }, BODY, 1790000000_000)).toBe(false);
    expect(await verifySvix(SECRET, { ...ok, signature: `v2,${sig}` }, BODY, 1790000000_000)).toBe(false);
    expect(await verifySvix(SECRET, { ...ok, signature: null }, BODY, 1790000000_000)).toBe(false);
    expect(await verifySvix("whsec_AAAAAAAAAAAAAAAAAAAAAAAA", ok, BODY, 1790000000_000)).toBe(false);
  });
});

describe("suppressionsFrom", () => {
  it("hard bounces and complaints suppress every recipient, lower-cased", () => {
    expect(suppressionsFrom(JSON.parse(BODY))).toEqual([{ email: "someone@example.com", reason: "bounce" }]);
    expect(suppressionsFrom({ type: "email.complained", data: { to: ["A <a@x.co>", "a@x.co"] } })).toEqual([{ email: "a@x.co", reason: "complaint" }]);
    expect(suppressionsFrom({ type: "email.suppressed", data: { to: "b@x.co" } })).toEqual([{ email: "b@x.co", reason: "bounce" }]);
  });
  it("ignores transient bounces, other events and junk", () => {
    expect(suppressionsFrom({ type: "email.bounced", data: { to: ["a@x.co"], bounce: { type: "Transient" } } })).toEqual([]);
    expect(suppressionsFrom({ type: "email.delivered", data: { to: ["a@x.co"] } })).toEqual([]);
    expect(suppressionsFrom({ type: "email.bounced", data: { to: ["not an address"] } })).toEqual([]);
    expect(suppressionsFrom("nope")).toEqual([]);
  });
});

describe("lifecycle env", () => {
  const base = { NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k", SUPABASE_SERVICE_ROLE_KEY: "svc" };
  it("the unsubscribe key falls back to the service-role key, domain-separated", () => {
    expect(readUnsubscribeSecret(undefined, "svc")).toBe("service-role:svc");
    expect(readUnsubscribeSecret("short", "svc")).toBe("service-role:svc");
    expect(readUnsubscribeSecret("x".repeat(32), "svc")).toBe("x".repeat(32));
  });
  it("the webhook route stays closed without a whsec_ secret", () => {
    expect(readResendWebhookSecret(undefined)).toBeNull();
    expect(readResendWebhookSecret("plain")).toBeNull();
    expect(readResendWebhookSecret(SECRET)).toBe(SECRET);
    expect(readServerConfig(base)?.lifecycleFrom).toBe("Valora3D <hello@valora3d.com>");
  });
});
