import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
import { signInAsGuest } from "./helpers";

async function check(page: Page) {
  // Wait for fonts and animations so contrast checks see the settled UI.
  await page.evaluate(() => document.fonts.ready);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

// The first spec of a full dev run hit "/" while Next was still compiling it and flaked;
// compile the page before any axe scan.
test.beforeAll(async ({ request }) => {
  await request.get("/", { timeout: 120_000 });
});

for (const path of ["/", "/pricing", "/login", "/signup", "/terms", "/privacy", "/contact", "/this-page-does-not-exist"]) {
  test(`axe: ${path}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await check(page);
  });
}

test("axe: Local studio, empty and with a model and scene controls", async ({ page }) => {
  test.setTimeout(240_000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signInAsGuest(page);
  await page.getByRole("button", { name: /new project/i }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: /^create$/i }).click();
  await expect(page.getByRole("button", { name: "Sample car" })).toBeVisible();
  await check(page);
  await page.getByRole("button", { name: "Sample car" }).click();
  await expect(page.locator("[data-model-loaded='true']")).toBeVisible({ timeout: 60_000 });
  const prompt = page.getByRole("textbox", { name: "Describe your render" });
  await prompt.fill("studio orbit around the car");
  await prompt.press("Enter");
  await expect(page.getByTestId("studio-status")).toHaveText("Scene ready · 1 version", { timeout: 30_000 });
  await check(page);
  await page.getByRole("button", { name: "Scene details" }).click();
  for (const tab of ["Analysis", "Controls", "Render"]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await check(page);
  }
});
