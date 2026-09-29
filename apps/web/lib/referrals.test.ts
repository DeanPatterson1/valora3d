import { describe, expect, it } from "vitest";
import { attributionFromVisit, decodeAttribution, encodeAttribution } from "@/lib/analytics/attribution";
import { REFERRAL_BONUS_CREDITS, REFERRAL_MONTHLY_CAP } from "@/lib/pricing";
import { lowBalance, renderCost } from "@/lib/render/cost";
import { REFERRAL_CODE, REFERRAL_TERMS_LINE, localReferralCode, referralLink, referralRef, toReferralSummary } from "./referrals";

describe("referral links", () => {
  it("builds /signup?ref=u_<code> on the site's origin", () => {
    expect(referralRef("abc123def4")).toBe("u_abc123def4");
    expect(referralLink("https://valora3d.com/", "abc123def4")).toBe("https://valora3d.com/signup?ref=u_abc123def4");
  });

  it("survives first-touch attribution unchanged (the database matches ref = u_<code>)", () => {
    const a = attributionFromVisit(new URL(referralLink("https://valora3d.com", "abc123def4")), null, new Date("2026-09-30T00:00:00Z"));
    expect(a).toMatchObject({ ref: "u_abc123def4", landing: "/signup" });
    expect(decodeAttribution(encodeAttribution(a!))?.ref).toBe("u_abc123def4");
  });

  it("states the terms with the real numbers", () => {
    expect(REFERRAL_TERMS_LINE).toContain(`you both get ${REFERRAL_BONUS_CREDITS} credits`);
    expect(REFERRAL_TERMS_LINE).toContain(`Up to ${REFERRAL_MONTHLY_CAP} rewards a month`);
    expect(REFERRAL_TERMS_LINE).toMatch(/first payment/);
  });

  it("validates the summary from the database or the API", () => {
    expect(toReferralSummary({ code: "abc123def4", joined: 2, qualified: 1, credits_earned: 100 })).toEqual({
      code: "abc123def4", joined: 2, qualified: 1, creditsEarned: 100,
    });
    expect(toReferralSummary({ code: "abc123def4", joined: 0, qualified: 0, creditsEarned: 0 })?.creditsEarned).toBe(0);
    expect(toReferralSummary({ code: "<script>", joined: 0, qualified: 0, credits_earned: 0 })).toBeNull();
    expect(toReferralSummary({ code: "abc123def4", joined: "x", qualified: 0, credits_earned: 0 })).toBeNull();
    expect(toReferralSummary(null)).toBeNull();
  });

  it("gives Local mode a stable, valid demo code", () => {
    const code = localReferralCode("local-user-1");
    expect(code).toMatch(REFERRAL_CODE);
    expect(localReferralCode("local-user-1")).toBe(code);
    expect(localReferralCode("local-user-2")).not.toBe(code);
  });
});

describe("low-balance math (the Render tab)", () => {
  const p = renderCost("preview");
  const f = renderCost("final");
  it("Free: counts Previews, never mentions a Final, links to credits only at zero", () => {
    expect(lowBalance(30, false)).toEqual({ text: "30 credits left: enough for 6 Previews.", getCredits: false });
    expect(lowBalance(p, false)).toEqual({ text: `${p} credits left: enough for 1 Preview.`, getCredits: false });
    expect(lowBalance(p - 1, false)).toEqual({ text: `${p - 1} credits left, not enough for a Preview (${p}).`, getCredits: true });
    expect(lowBalance(1, false)?.text).toBe(`1 credit left, not enough for a Preview (${p}).`);
    for (const b of [0, 5, 30, 500, 5000]) expect(lowBalance(b, false)?.text ?? "").not.toMatch(/final/i);
  });
  it("Creator/Pro: quiet until a Final is out of reach", () => {
    expect(lowBalance(f, true)).toBeNull();
    expect(lowBalance(f - 1, true)).toEqual({ text: `${f - 1} credits left: enough for ${Math.floor((f - 1) / p)} Previews. A Final uses ${f}.`, getCredits: true });
    expect(lowBalance(0, true)).toEqual({ text: `0 credits left, not enough for a Preview (${p}) or a Final (${f}).`, getCredits: true });
  });
});
