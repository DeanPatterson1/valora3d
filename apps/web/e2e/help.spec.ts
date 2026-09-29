import { test, expect } from "./fixtures";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { HELP_ARTICLES, HELP_FAQS } from "../lib/help";
import { signInAsGuest } from "./helpers";

test("help search, FAQ structured data and article navigation", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/help");
  await expect(page).toHaveTitle("Help center · Valora3D");
  const articles = page.getByRole("region", { name: "Help articles" });
  await expect(articles.getByRole("link")).toHaveCount(8);
  await page.getByRole("searchbox").fill("  Paddle  ");
  await expect(articles.getByRole("link")).toHaveCount(1);
  await articles.getByRole("link").click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Credits, plans and refunds");
  await page.getByRole("link", { name: "All help articles" }).click();
  await page.getByRole("searchbox").fill("no-such-topic");
  await expect(page.getByRole("heading", { name: "No matching articles" })).toBeVisible();
  await page.getByRole("button", { name: "Clear search" }).click();
  await expect(articles.getByRole("link")).toHaveCount(8);
  const schema = JSON.parse(await page.locator('script[type="application/ld+json"]').textContent() ?? "{}");
  expect(schema.mainEntity).toHaveLength(HELP_FAQS.length);
  for (const faq of HELP_FAQS) {
    await page.getByText(faq.question, { exact: true }).click();
    await expect(page.getByText(faq.answer, { exact: true })).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("all articles are public, accessible and fit desktop and phone", async ({ page }) => {
  test.setTimeout(240_000);
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    const routes = [{ slug: "", title: "Your next shot starts here." }, ...HELP_ARTICLES];
    for (const article of routes) {
      const route = `/help${article.slug ? `/${article.slug}` : ""}`;
      expect((await page.goto(route))?.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(article.title);
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `https://valora3d.com${route}`);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      if (process.env.HELP_SHOTS_DIR) {
        await mkdir(process.env.HELP_SHOTS_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.HELP_SHOTS_DIR, `help-${article.slug || "index"}-${viewport.width === 390 ? "phone" : "desktop"}.png`), fullPage: true });
      }
    }
  }
  expect((await page.goto("/help/not-an-article"))?.status()).toBe(404);
});

test("help entry links work from landing, sidebar and upload card", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Footer" }).getByRole("link", { name: "Help", exact: true })).toHaveAttribute("href", "/help");
  await page.mouse.wheel(0, 2000);
  await page.getByRole("navigation", { name: "Landing" }).getByRole("link", { name: "Help", exact: true }).click();
  await expect(page).toHaveURL(/\/help$/);
  await signInAsGuest(page);
  await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Help", exact: true })).toHaveAttribute("href", "/help");
  await page.getByRole("button", { name: /new project/i }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: /^create$/i }).click();
  await page.getByRole("link", { name: "How to export a .glb" }).click();
  await expect(page).toHaveURL(/\/help\/preparing-your-model#blender$/);
});

test("sitemap and install icons are served with the declared sizes", async ({ request, page }) => {
  const sitemap = await (await request.get("/sitemap.xml")).text();
  for (const article of HELP_ARTICLES) expect(sitemap).toContain(`/help/${article.slug}`);
  const manifest = await (await request.get("/manifest.webmanifest")).json();
  for (const icon of manifest.icons) {
    const response = await request.get(icon.src);
    expect(response.ok()).toBe(true);
    if (icon.type === "image/png") {
      const png = await response.body();
      expect(`${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`).toBe(icon.sizes);
    }
  }
  await page.goto("/help");
  const apple = await page.locator('link[rel="apple-touch-icon"]').getAttribute("href");
  const png = await (await request.get(apple!)).body();
  expect([png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([180, 180]);
});
