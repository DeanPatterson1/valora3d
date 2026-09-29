import { describe, expect, it } from "vitest";
import { authCallbackUrl, checkoutPath, loginHref, nextFromParams, nextFromRedirectTo, signupHref, START_PATH } from "./next";
import { parseConfirmLink } from "@/lib/auth/emailLink";

const q = (s: string) => new URLSearchParams(s);

describe("signup / login destinations (lib/nav/next.ts)", () => {
  it("sends a new visitor to signup, then a new project", () => {
    expect(signupHref()).toBe("/signup?next=%2Fprojects%3Fnew%3D1");
    expect(nextFromParams(q(signupHref().split("?")[1]))).toBe(START_PATH);
  });

  it("turns a chosen plan or pack into that item's checkout after signup", () => {
    expect(signupHref(undefined, "plan:creator")).toBe("/signup?next=%2Fpricing%3Fcheckout%3Dplan%253Acreator");
    expect(nextFromParams(q(signupHref(undefined, "plan:creator").split("?")[1]))).toBe(checkoutPath("plan:creator"));
    expect(nextFromParams(q("plan=pro"))).toBe(checkoutPath("plan:pro"));
    expect(nextFromParams(q("pack=600"))).toBe(checkoutPath("pack:600"));
    // Unknown items are ignored, never passed through.
    expect(nextFromParams(q("plan=enterprise"))).toBe("/projects");
    expect(nextFromParams(q("pack=7"))).toBe("/projects");
  });

  it("never lets next leave the site", () => {
    for (const evil of ["//evil.example", "https://evil.example", "/\evil.example", "/%09/evil.example", "javascript:alert(1)"]) {
      const next = nextFromParams(q(`next=${encodeURIComponent(evil)}`));
      // Whatever survives is a path on this site: resolving it can never change the origin.
      expect(new URL(next, "https://valora3d.com").origin, evil).toBe("https://valora3d.com");
      expect(next.startsWith("//"), evil).toBe(false);
    }
  });

  it("keeps the default link bare and cross-links login and signup with the same destination", () => {
    expect(loginHref(null)).toBe("/login");
    expect(loginHref("/projects")).toBe("/login");
    expect(loginHref(checkoutPath("pack:250"))).toBe("/login?next=%2Fpricing%3Fcheckout%3Dpack%253A250");
    expect(signupHref("/projects")).toBe("/signup");
  });

  it("builds the OAuth / email callback with a safe next", () => {
    expect(authCallbackUrl("https://valora3d.com", checkoutPath("plan:creator"))).toBe(
      "https://valora3d.com/auth/callback?next=%2Fpricing%3Fcheckout%3Dplan%253Acreator",
    );
    expect(authCallbackUrl("https://valora3d.com", "//evil.example")).toBe("https://valora3d.com/auth/callback?next=%2Fprojects");
  });

  it("reads next back out of the confirmation email's {{ .RedirectTo }}, keeping only a path", () => {
    const redirectTo = authCallbackUrl("https://valora3d.com", checkoutPath("plan:creator"));
    // The template drops RedirectTo into the link unencoded; the browser/URL parser decodes it once.
    const link = `https://valora3d.com/auth/confirm?token_hash=${"a".repeat(32)}&type=email&next=${redirectTo}`;
    const parsed = parseConfirmLink((k) => new URL(link).searchParams.get(k));
    expect(parsed?.next).toBe("/pricing?checkout=plan:creator");
    // Not on the allow list: Supabase sends the Site URL, which falls back to the default.
    expect(nextFromRedirectTo("https://valora3d.com")).toBe("/projects");
    expect(nextFromRedirectTo("https://valora3d.com/")).toBe("/projects");
    // A foreign origin only ever contributes a path on this site.
    expect(nextFromRedirectTo("https://evil.example/pricing")).toBe("/pricing");
    expect(nextFromRedirectTo("https://evil.example/auth/callback?next=//evil.example")).toBe("/projects");
    expect(nextFromRedirectTo("javascript:alert(1)")).toBe("/projects");
    expect(nextFromRedirectTo("/projects?new=1")).toBe("/projects?new=1");
  });
});
