// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  attributionCookieHeader,
  attributionForCheckout,
  attributionFromCheckout,
  attributionFromVisit,
  decodeAttribution,
  encodeAttribution,
  shouldCaptureAttribution,
} from "./attribution";

const NOW = new Date("2026-09-30T10:00:00Z");
const visit = (url: string, referer: string | null = null) => attributionFromVisit(new URL(url), referer, NOW);
const b64 = (s: string) => Buffer.from(s).toString("base64url");

describe("first-touch attribution", () => {
  it("reads utm parameters, ref and the referring host, as short plain tokens", () => {
    expect(visit("https://valora3d.com/pricing?utm_source=Newsletter&utm_medium=email&utm_campaign=Spring%20Launch!&x=1")).toEqual({
      source: "newsletter",
      medium: "email",
      campaign: "spring-launch",
      landing: "/pricing",
      at: "2026-09-30",
    });
    expect(visit("https://valora3d.com/signup?ref=share_AbCdEfGhIjKlMnOpQrStUvWx")).toMatchObject({
      ref: "share_AbCdEfGhIjKlMnOpQrStUvWx",
      landing: "/signup",
    });
    expect(visit("https://valora3d.com/", "https://www.reddit.com/r/blender/comments/abc?user=me")).toMatchObject({
      referrer: "reddit.com",
      landing: "/",
    });
  });

  it("ignores direct visits and our own site as a referrer", () => {
    expect(visit("https://valora3d.com/")).toBeNull();
    expect(visit("https://valora3d.com/pricing", "https://valora3d.com/")).toBeNull();
    expect(visit("https://valora3d.com/pricing", "https://www.valora3d.com/help")).toBeNull();
    expect(visit("https://valora3d.com/", "android-app://com.google")).toBeNull();
  });

  it("round-trips through the cookie and refuses tampered or oversized values", () => {
    const a = visit("https://valora3d.com/?utm_source=x&ref=abc")!;
    expect(decodeAttribution(encodeAttribution(a))).toEqual(a);
    expect(decodeAttribution("not base64!")).toBeNull();
    expect(decodeAttribution(b64(JSON.stringify({ source: "<script>", evil: "x" })))).toEqual({ source: "script" });
    expect(decodeAttribution("A".repeat(900))).toBeNull();
    expect(decodeAttribution(b64("[1,2]"))).toBeNull();
  });

  it("sets a first-party, 90-day, Lax, HttpOnly cookie", () => {
    const header = attributionCookieHeader({ source: "x" }, true);
    expect(header).toMatch(/^v3d_src=[A-Za-z0-9_-]+; Path=\/; Max-Age=7776000; SameSite=Lax; HttpOnly; Secure$/);
    expect(attributionCookieHeader({ source: "x" }, false)).not.toContain("Secure");
  });

  it("captures only top-level page visits without a cookie or a privacy signal", () => {
    const h = (o: Record<string, string> = {}) => new Headers(o);
    const base = { method: "GET", pathname: "/", headers: h({ "sec-fetch-dest": "document" }), hasCookie: false };
    expect(shouldCaptureAttribution(base)).toBe(true);
    expect(shouldCaptureAttribution({ ...base, hasCookie: true })).toBe(false);
    expect(shouldCaptureAttribution({ ...base, method: "POST" })).toBe(false);
    expect(shouldCaptureAttribution({ ...base, pathname: "/api/events" })).toBe(false);
    expect(shouldCaptureAttribution({ ...base, headers: h({ "sec-gpc": "1" }) })).toBe(false);
    expect(shouldCaptureAttribution({ ...base, headers: h({ rsc: "1" }) })).toBe(false);
    expect(shouldCaptureAttribution({ ...base, headers: h({ "next-router-prefetch": "1" }) })).toBe(false);
    expect(shouldCaptureAttribution({ ...base, headers: h({ "sec-fetch-dest": "image" }) })).toBe(false);
  });

  it("travels through Paddle custom data as compact JSON and is re-validated on the way back", () => {
    const src = attributionForCheckout({ source: "newsletter", ref: "share_x", at: "2026-09-30" });
    expect(src).toBe('{"source":"newsletter","ref":"share_x"}');
    expect(attributionFromCheckout(src)).toEqual({ source: "newsletter", ref: "share_x" });
    expect(attributionForCheckout(null)).toBeNull();
    expect(attributionFromCheckout("{not json")).toBeNull();
    expect(attributionFromCheckout(42)).toBeNull();
  });
});
