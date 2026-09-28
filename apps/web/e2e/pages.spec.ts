import { test, expect } from "@playwright/test";
import { signInAsGuest } from "./helpers";

const trustPages = [
  ["/terms", "Terms of service"], ["/privacy", "Privacy notice"],
  ["/acceptable-use", "Acceptable use"], ["/refunds", "Refunds and cancellation"],
  ["/contact", "Contact"],
] as const;

test("landing: launch copy, footer, navigation, fonts and hero playback", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("You don't need to know Blender.");
  await expect(page.getByText("Example shot · rendered with Blender Cycles")).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /Reviews/ })).toHaveCount(0);
  const video = page.getByTestId("hero-video");
  await expect.poll(() => video.evaluate((el: HTMLVideoElement) => !el.paused && el.readyState >= 2)).toBe(true);
  await page.getByRole("button", { name: "Pause background video" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Play background video" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Landing" });
  await page.mouse.wheel(0, 2000);
  await expect(nav).toHaveAttribute("data-visible", "true");
  await expect(nav).toHaveCSS("opacity", "1");
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(nav).not.toHaveAttribute("data-visible");
  expect(await video.evaluate((el: HTMLVideoElement) => el.paused)).toBe(true);
  await page.getByRole("button", { name: "Play background video" }).click();
  await expect.poll(() => video.evaluate((el: HTMLVideoElement) => !el.paused)).toBe(true);
  for (const [path] of trustPages) await expect(page.getByRole("navigation", { name: "Footer" }).locator(`a[href="${path}"]`)).toBeAttached();
  await expect(page.locator("body")).not.toContainText(/prototype|not connected|nothing is uploaded/i);
  await expect.poll(() => page.evaluate(() => Array.from(document.fonts).some((font) => font.family.includes("Inter") && font.status === "loaded"))).toBe(true);
  expect(errors).toEqual([]);
});

test("reduced motion pauses the hero until explicitly played", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const video = page.getByTestId("hero-video");
  await expect(page.getByRole("button", { name: "Play background video" })).toBeVisible();
  expect(await video.evaluate((el: HTMLVideoElement) => el.paused)).toBe(true);
  await page.getByRole("button", { name: "Play background video" }).click();
  await expect.poll(() => video.evaluate((el: HTMLVideoElement) => !el.paused)).toBe(true);
});

test("pricing is public and signed-out actions lead to signup", async ({ page }) => {
  const response = await page.goto("/pricing");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveURL(/\/pricing$/);
  await expect(page.getByRole("heading", { level: 1, name: "Plans" })).toBeVisible();
  const plans = page.getByRole("list", { name: "Plans", exact: true });
  await expect(plans.getByRole("link", { name: /Get started/ })).toHaveCount(3);
  await expect(page.getByRole("list", { name: "Credit packs" }).getByRole("link", { name: /Get started/ })).toHaveCount(3);
  await plans.getByRole("link", { name: "Get started: Creator", exact: true }).click();
  await expect(page).toHaveURL(/\/signup$/);
});

test("pricing retains existing signed-in plan actions", async ({ page }) => {
  await signInAsGuest(page, "/pricing");
  await page.getByRole("button", { name: "Choose plan: Creator" }).click();
  await expect(page.getByRole("status").getByText("Added 500 credits")).toBeVisible();
});

for (const [path, title] of trustPages) {
  test(`${path}: public draft, contact, metadata and footer`, async ({ page }) => {
    expect((await page.goto(path))?.status()).toBe(200);
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { level: 1, name: title, exact: true })).toBeVisible();
    await expect(page.getByText("Draft — pending owner review")).toBeVisible();
    await expect(page.getByText("Effective date: [To be confirmed by owner]")).toBeVisible();
    await expect(page.locator('a[href="mailto:support@valora3d.com"]').first()).toBeAttached();
    await expect(page).toHaveTitle(title);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /.+/);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `https://valora3d.com${path}`);
    for (const [href] of trustPages) await expect(page.getByRole("navigation", { name: "Footer" }).locator(`a[href="${href}"]`)).toBeVisible();
  });
}

test("unknown route returns the styled 404 and a working home link", async ({ page }) => {
  expect((await page.goto("/this-page-does-not-exist"))?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await page.getByRole("link", { name: "Back to home" }).click();
  await expect(page).toHaveURL("/");
});

test("SEO endpoints list public pages and serve the default share image", async ({ page, request }) => {
  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.ok()).toBe(true);
  const xml = await sitemap.text();
  for (const [path] of trustPages) expect(xml).toContain(`https://valora3d.com${path}`);
  expect(xml).toContain("https://valora3d.com/pricing");
  expect(xml).not.toMatch(/\/projects|\/dev|\/settings|\/profile|\/login|\/signup/);
  expect(await (await request.get("/robots.txt")).text()).toContain("Sitemap: https://valora3d.com/sitemap.xml");
  expect(await (await request.get("/manifest.webmanifest")).json()).toMatchObject({ name: "Valora3D", start_url: "/" });
  await page.goto("/pricing");
  const image = await page.locator('meta[property="og:image"]').getAttribute("content");
  expect(image).toMatch(/^https:\/\/valora3d.com\/opengraph-image/);
  const imageResponse = await request.get(new URL(image!).pathname);
  expect(imageResponse.ok()).toBe(true);
  expect(imageResponse.headers()["content-type"]).toContain("image/png");
});

test("security headers cover public responses", async ({ request }) => {
  const headers = (await request.get("/pricing")).headers();
  expect(headers["strict-transport-security"]).toContain("max-age=31536000");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["permissions-policy"]).toContain("camera=()");
  const csp = headers["content-security-policy"];
  const directives = Object.fromEntries(csp.split(";").map((entry) => entry.trim().split(/\s+/)).map(([name, ...sources]) => [name, sources]));
  expect(directives["script-src"]).toContain("https://challenges.cloudflare.com");
  expect(directives["frame-src"]).toContain("https://challenges.cloudflare.com");
  expect(directives["script-src"]).toContain("https://static.cloudflareinsights.com");
  expect(directives["connect-src"]).toContain("https://cloudflareinsights.com");
  for (const source of ["frame-ancestors 'none'", "https://*.supabase.co", "wss://*.supabase.co", "https://*.paddle.com", "https://cdn.paddle.com", "https://challenges.cloudflare.com", "https://*.r2.cloudflarestorage.com", "blob:", "data:"]) expect(csp).toContain(source);
  if (process.env.E2E_PRODUCTION === "1") expect(csp).not.toContain("'unsafe-eval'");
});

test("production dev routes return 404 without requiring sign-in", async ({ page }) => {
  test.skip(process.env.E2E_PRODUCTION !== "1", "Run with E2E_PRODUCTION=1 to check the production server.");
  for (const path of ["/dev/viewer", "/dev/tokens", "/dev/render-states", "/dev/missing"]) {
    expect((await page.goto(path))?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
  }
});
