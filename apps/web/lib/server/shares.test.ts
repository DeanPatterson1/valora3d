import { describe, expect, it, vi } from "vitest";
import nextConfig from "../../next.config";
import robots from "../../app/robots";
import sitemap from "../../app/sitemap";
import { goneHtml, goneResponse, reportHref, shareMetadata, videoSize } from "@/lib/share/public";
import { isShareSlug, newShareSlug, SHARE_SLUG_BYTES } from "@/lib/share/slug";
import type { PublicShare } from "@/lib/share/types";
import { lookupPublicShare, type PublicShareRow } from "./shareLookup";
import { createShare, getShare, revokeShare, shareMedia, type RenderShareRow, type ShareStore } from "./shares";

const JOB = "11111111-2222-4333-8444-555555555555";
const OWNER = "aaaaaaaa-0000-0000-0000-000000000001";
const SLUG = "AbCdEfGhIjKlMnOpQrStUv12";

function shareRow(over: Partial<RenderShareRow> = {}): RenderShareRow {
  return {
    id: "s1", slug: SLUG, job_id: JOB, user_id: OWNER, show_prompt: false,
    created_at: "2026-09-29T10:00:00Z", revoked_at: null, view_count: "3", ...over,
  };
}

const LIVE: PublicShareRow = {
  state: "live", job_id: JOB, user_id: OWNER, kind: "preview", prompt: "red car at dusk", aspect: "9:16", width: 540, height: 960,
};

function store(over: Partial<ShareStore> = {}): ShareStore {
  return {
    ownedJob: vi.fn(async () => ({ id: JOB, status: "succeeded", expired_at: null })),
    liveShare: vi.fn(async () => null),
    create: vi.fn(async (_u: string, _j: string, slug: string, showPrompt: boolean) => ({ row: shareRow({ slug, show_prompt: showPrompt }) })),
    revoke: vi.fn(async () => 1),
    publicRead: vi.fn(async () => LIVE),
    bumpView: vi.fn(async () => {}),
    ...over,
  };
}

describe("share slugs", () => {
  it("are 24 base64url characters from 18 random bytes (144 bits)", () => {
    expect(SHARE_SLUG_BYTES * 8).toBeGreaterThanOrEqual(128);
    for (let i = 0; i < 200; i++) {
      const s = newShareSlug();
      expect(s).toMatch(/^[A-Za-z0-9_-]{24}$/);
      expect(isShareSlug(s)).toBe(true);
    }
  });
  it("never repeat and use the whole alphabet evenly", () => {
    const seen = new Set<string>();
    const counts = new Map<string, number>();
    const N = 5000;
    for (let i = 0; i < N; i++) {
      const s = newShareSlug();
      seen.add(s);
      for (const c of s) counts.set(c, (counts.get(c) ?? 0) + 1);
    }
    expect(seen.size).toBe(N);
    expect(counts.size).toBe(64);
    // 120k characters over 64 symbols: ~1875 each. A biased generator would sit far outside this band.
    for (const n of counts.values()) {
      expect(n).toBeGreaterThan(1500);
      expect(n).toBeLessThan(2250);
    }
  });
  it("come from the injected random source (Web Crypto by default)", () => {
    const zero = newShareSlug((b) => b.fill(0));
    expect(zero).toBe("A".repeat(24));
    const spy = vi.spyOn(crypto, "getRandomValues");
    newShareSlug();
    expect(spy).toHaveBeenCalledOnce();
    spy.mockRestore();
  });
  it("reject short, long and non-URL-safe values", () => {
    expect(isShareSlug("a".repeat(21))).toBe(false);
    expect(isShareSlug("a".repeat(65))).toBe(false);
    expect(isShareSlug(`${"a".repeat(22)}/`)).toBe(false);
    expect(isShareSlug(`${"a".repeat(22)}=`)).toBe(false);
    expect(isShareSlug(42)).toBe(false);
  });
});

describe("owner routes", () => {
  it("GET returns the caller's live link", async () => {
    const s = store({ liveShare: vi.fn(async () => shareRow({ show_prompt: true })) });
    const res = await getShare(s, JOB);
    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(await res.json()).toEqual({
      share: { slug: SLUG, path: `/r/${SLUG}`, showPrompt: true, createdAt: Date.parse("2026-09-29T10:00:00Z"), viewCount: 3 },
    });
  });
  it("someone else's render (invisible through RLS) is a 404 for every verb, and nothing is written", async () => {
    const s = store({ ownedJob: vi.fn(async () => null) });
    expect((await getShare(s, JOB)).status).toBe(404);
    expect((await createShare(s, OWNER, JOB, { show_prompt: false })).status).toBe(404);
    expect((await revokeShare(s, OWNER, JOB)).status).toBe(404);
    expect(s.create).not.toHaveBeenCalled();
    expect(s.revoke).not.toHaveBeenCalled();
  });
  it("a malformed job id never reaches the store", async () => {
    const s = store();
    expect((await createShare(s, OWNER, "not-a-uuid", { show_prompt: false })).status).toBe(404);
    expect(s.ownedJob).not.toHaveBeenCalled();
  });
  it("creates with a fresh random slug for the caller", async () => {
    const s = store();
    const res = await createShare(s, OWNER, JOB, { show_prompt: true });
    expect(res.status).toBe(200);
    const { share } = await res.json();
    expect(isShareSlug(share.slug)).toBe(true);
    expect(share.showPrompt).toBe(true);
    expect(s.create).toHaveBeenCalledWith(OWNER, JOB, share.slug, true);
  });
  it("refuses a render that is not finished or has expired", async () => {
    const running = store({ ownedJob: vi.fn(async () => ({ id: JOB, status: "running", expired_at: null })) });
    expect((await createShare(running, OWNER, JOB, { show_prompt: false })).status).toBe(409);
    const expired = store({ ownedJob: vi.fn(async () => ({ id: JOB, status: "succeeded", expired_at: "2026-09-20T00:00:00Z" })) });
    const res = await createShare(expired, OWNER, JOB, { show_prompt: false });
    expect(res.status).toBe(409);
    expect((await res.json()).error.code).toBe("not_shareable");
    expect(expired.create).not.toHaveBeenCalled();
  });
  it("maps the SQL rate limit to 429 and past-retention to 409", async () => {
    const limited = store({ create: vi.fn(async () => ({ error: { code: "P0001", message: "rate_limited: max 20" } })) });
    const r1 = await createShare(limited, OWNER, JOB, { show_prompt: false });
    expect(r1.status).toBe(429);
    expect((await r1.json()).error.code).toBe("rate_limited");
    const stale = store({ create: vi.fn(async () => ({ error: { code: "P0001", message: "not_shareable" } })) });
    expect((await createShare(stale, OWNER, JOB, { show_prompt: false })).status).toBe(409);
  });
  it("retries a slug collision once with a new slug", async () => {
    const create = vi
      .fn<ShareStore["create"]>()
      .mockResolvedValueOnce({ error: { code: "23505", message: "duplicate key" } })
      .mockImplementation(async (_u, _j, slug) => ({ row: shareRow({ slug }) }));
    const slugs = ["a".repeat(24), "b".repeat(24)];
    const res = await createShare(store({ create }), OWNER, JOB, { show_prompt: false }, () => slugs.shift()!);
    expect(res.status).toBe(200);
    expect(create.mock.calls.map((c) => c[2])).toEqual(["a".repeat(24), "b".repeat(24)]);
  });
  it("revoke is scoped to the caller and idempotent", async () => {
    const s = store({ revoke: vi.fn(async () => 0) });
    const res = await revokeShare(s, OWNER, JOB);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ share: null });
    expect(s.revoke).toHaveBeenCalledWith(OWNER, JOB);
  });
});

describe("public lookup", () => {
  it("a live share exposes only what the page shows", async () => {
    const found = await lookupPublicShare(store(), SLUG);
    expect(found).toEqual({
      state: "live", jobId: JOB, userId: OWNER,
      share: { slug: SLUG, kind: "preview", prompt: "red car at dusk", width: 540, height: 960 },
    });
  });
  it("revoked and expired are gone; unknown and malformed are missing", async () => {
    expect(await lookupPublicShare(store({ publicRead: vi.fn(async () => ({ ...LIVE, state: "revoked" as const })) }), SLUG))
      .toEqual({ state: "gone", reason: "revoked" });
    expect(await lookupPublicShare(store({ publicRead: vi.fn(async () => ({ ...LIVE, state: "expired" as const })) }), SLUG))
      .toEqual({ state: "gone", reason: "expired" });
    expect(await lookupPublicShare(store({ publicRead: vi.fn(async () => null) }), SLUG)).toEqual({ state: "missing" });
    const s = store();
    expect(await lookupPublicShare(s, "../../etc/passwd")).toEqual({ state: "missing" });
    expect(s.publicRead).not.toHaveBeenCalled();
  });
  it("a blank prompt is no prompt", async () => {
    const found = await lookupPublicShare(store({ publicRead: vi.fn(async () => ({ ...LIVE, prompt: "  " })) }), SLUG);
    expect(found.state === "live" && found.share.prompt).toBeNull();
  });
});

describe("public media route", () => {
  const presign = vi.fn(async (key: string, seconds: number, r: { contentType: string; disposition: string }) =>
    `https://acct.r2.cloudflarestorage.com/b/${key}?X-Amz-Expires=${seconds}&ct=${r.contentType}&cd=${r.disposition}`);

  it("redirects a live video to a short-lived inline R2 link under the owner's prefix", async () => {
    const res = await shareMedia(store(), presign, SLUG, "video");
    expect(res.status).toBe(302);
    const location = res.headers.get("location")!;
    expect(location).toContain(`r/${OWNER}/${JOB}/video.mp4`);
    expect(location).toContain("ct=video/mp4");
    expect(location).toContain("cd=inline");
    expect(presign.mock.calls.at(-1)![1]).toBeLessThanOrEqual(900);
    expect(res.headers.get("cache-control")).toBe("private, max-age=120");
    expect(res.headers.get("x-robots-tag")).toContain("noindex");
  });
  it("serves the poster as an image", async () => {
    const res = await shareMedia(store(), presign, SLUG, "poster");
    expect(res.headers.get("location")).toContain("poster.jpg");
  });
  it("answers 410 once revoked or expired, without signing anything", async () => {
    presign.mockClear();
    for (const state of ["revoked", "expired"] as const) {
      const res = await shareMedia(store({ publicRead: vi.fn(async () => ({ ...LIVE, state })) }), presign, SLUG, "video");
      expect(res.status).toBe(410);
    }
    expect(presign).not.toHaveBeenCalled();
  });
  it("404s an unknown slug or file name", async () => {
    expect((await shareMedia(store({ publicRead: vi.fn(async () => null) }), presign, SLUG, "video")).status).toBe(404);
    expect((await shareMedia(store(), presign, SLUG, "frames_zip")).status).toBe(404);
    expect((await shareMedia(store(), presign, SLUG, "__proto__")).status).toBe(404);
  });
});

describe("share metadata", () => {
  const share: PublicShare = { slug: SLUG, kind: "final", prompt: "a <b>bold</b> car", width: 1920, height: 1080 };

  it("describes a video.other with og:video, secure_url, type and size, and the poster as og:image", () => {
    const m = shareMetadata(share, "https://valora3d.com");
    const og = m.openGraph as Record<string, unknown>;
    expect(og.type).toBe("video.other");
    expect(og.url).toBe(`https://valora3d.com/r/${SLUG}`);
    expect(og.videos).toEqual([{
      url: `https://valora3d.com/r/${SLUG}/video`,
      secureUrl: `https://valora3d.com/r/${SLUG}/video`,
      type: "video/mp4", width: 1920, height: 1080,
    }]);
    expect(og.images).toEqual([expect.objectContaining({ url: `https://valora3d.com/r/${SLUG}/poster`, width: 1920, height: 1080 })]);
    expect(m.twitter).toEqual(expect.objectContaining({ card: "summary_large_image", images: [`https://valora3d.com/r/${SLUG}/poster`] }));
  });
  it("is always noindex", () => {
    expect(shareMetadata(share).robots).toEqual(expect.objectContaining({ index: false, follow: false }));
  });
  it("quotes the prompt only when the owner showed it", () => {
    expect(shareMetadata(share).description).toContain("a <b>bold</b> car");
    const hidden = shareMetadata({ ...share, prompt: null });
    expect(hidden.description).not.toContain("bold");
    expect(JSON.stringify(hidden)).not.toContain("bold");
  });
  it("clips a long prompt", () => {
    expect(String(shareMetadata({ ...share, prompt: "x".repeat(2000) }).description).length).toBeLessThanOrEqual(200);
  });
  it("sizes the video from the worker's report, else from tier and aspect", () => {
    expect(videoSize("preview", "9:16", 540, 960)).toEqual({ width: 540, height: 960 });
    expect(videoSize("preview", null)).toEqual({ width: 540, height: 960 });
    expect(videoSize("final", "16:9")).toEqual({ width: 1920, height: 1080 });
    expect(videoSize("final", "9:16", 0, null)).toEqual({ width: 1080, height: 1920 });
  });
});

describe("gone page and site rules", () => {
  it("is a friendly, noindex 410", async () => {
    const res = goneResponse("revoked");
    expect(res.status).toBe(410);
    expect(res.headers.get("content-type")).toContain("text/html");
    expect(res.headers.get("x-robots-tag")).toContain("noindex");
    const html = await res.text();
    expect(html).toContain("no longer available");
    expect(html).toContain("stopped sharing");
    expect(html).toContain('name="robots" content="noindex, nofollow"');
    expect(html).toContain('href="/signup"');
    expect(goneHtml("expired")).toContain("expired");
  });
  it("report links carry the slug and nothing else about the viewer", () => {
    const href = reportHref(SLUG);
    expect(href.startsWith("mailto:support@valora3d.com?")).toBe(true);
    expect(decodeURIComponent(href)).toContain(SLUG);
  });
  it("robots disallow /r/ and the sitemap leaves shares out", () => {
    const rules = robots().rules as { disallow: string[] };
    expect(rules.disallow).toContain("/r/");
    expect(sitemap().some((e) => e.url.includes("/r/"))).toBe(false);
  });
  it("the CSP lets the video and poster load from R2 after the redirect", async () => {
    const rules = await nextConfig.headers!();
    const csp = rules[0].headers.find((h) => h.key === "Content-Security-Policy")!.value;
    const directive = (name: string) => csp.split(";").map((d) => d.trim()).find((d) => d.startsWith(`${name} `)) ?? "";
    expect(directive("media-src")).toContain("https://*.r2.cloudflarestorage.com");
    expect(directive("img-src")).toContain("https://*.r2.cloudflarestorage.com");
  });
});
