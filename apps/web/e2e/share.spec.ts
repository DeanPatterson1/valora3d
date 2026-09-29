import { test, expect } from "@playwright/test";
import { signInAsGuest } from "./helpers";

const SLUG = "fixtureFixtureFixture123";
const meta = (page: import("@playwright/test").Page, attr: "property" | "name", key: string) =>
  page.locator(`meta[${attr}="${key}"]`).first().getAttribute("content");

test("share page: video, prompt, CTA, report link and video metadata", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/dev/share-page");
  await expect(page.getByLabel("Shared render")).toBeVisible();
  await expect(page.getByText("A silver sports car on a wet road at dusk", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "Try Valora3D free" })).toHaveAttribute("href", "/signup");
  const report = await page.getByRole("link", { name: "Report this video" }).getAttribute("href");
  expect(report).toMatch(/^mailto:support@valora3d\.com\?/);
  expect(decodeURIComponent(report!)).toContain(SLUG);

  expect(await meta(page, "property", "og:type")).toBe("video.other");
  expect(await meta(page, "property", "og:video")).toMatch(new RegExp(`/r/${SLUG}/video$`));
  expect(await meta(page, "property", "og:video:secure_url")).toMatch(/^https:\/\/.+\/video$/);
  expect(await meta(page, "property", "og:video:type")).toBe("video/mp4");
  expect(await meta(page, "property", "og:video:width")).toBe("1920");
  expect(await meta(page, "property", "og:video:height")).toBe("1080");
  expect(await meta(page, "property", "og:image")).toMatch(new RegExp(`/r/${SLUG}/poster$`));
  expect(await meta(page, "name", "twitter:card")).toBe("summary_large_image");
  expect(await meta(page, "name", "robots")).toContain("noindex");
  expect(errors).toEqual([]);
});

test("share page: a hidden prompt never reaches the page or its metadata", async ({ page }) => {
  await page.goto("/dev/share-page?prompt=0&layout=portrait");
  await expect(page.getByLabel("Shared render")).toBeVisible();
  expect(await page.content()).not.toContain("silver sports car");
  expect(await meta(page, "property", "og:video:height")).toBe("960");
});

test("share links: unknown is 404, gone is a friendly 410, robots keep /r/ out", async ({ page, request }) => {
  const missing = await page.goto("/r/AAAAAAAAAAAAAAAAAAAAAAAA");
  expect(missing?.status()).toBe(404);
  expect(await meta(page, "name", "robots")).toContain("noindex");
  expect((await request.get("/r/AAAAAAAAAAAAAAAAAAAAAAAA/video", { maxRedirects: 0 })).status()).toBe(404);

  const gone = await page.goto("/dev/share-page/gone?reason=revoked");
  expect(gone?.status()).toBe(410);
  await expect(page.getByRole("heading", { name: "This render is no longer available" })).toBeVisible();
  await expect(page.getByText("stopped sharing")).toBeVisible();
  await expect(page.getByRole("link", { name: "Make your own with Valora3D" })).toHaveAttribute("href", "/signup");

  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain("Disallow: /r/");
  expect(await (await request.get("/sitemap.xml")).text()).not.toContain("/r/");
});

test("studio result: Share creates a link, copies it and can stop sharing", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await signInAsGuest(page, "/dev/render-states");
  const result = page.getByRole("region", { name: "Render result" }).first();
  await result.getByRole("button", { name: "Share" }).click();
  await result.getByRole("button", { name: "Create link" }).click();
  const link = result.getByLabel("Share link");
  await expect(link).toHaveValue(/\/dev\/share-page$/);
  await expect(page.getByText("Link created and copied.")).toBeVisible();
  await result.getByRole("button", { name: "Stop sharing" }).click();
  await expect(result.getByRole("button", { name: "Create link" })).toBeVisible();
});

for (const path of ["/dev/share-page", "/dev/share-page?layout=portrait&prompt=0", "/dev/share-page/gone?reason=expired"]) {
  test(`axe: ${path}`, async ({ page }) => {
    const { default: AxeBuilder } = await import("@axe-core/playwright");
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(path);
    await page.evaluate(() => document.fonts.ready);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
}
