import { test, expect } from "@playwright/test";

test("landing renders the headline and exactly one canvas", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("You don't need to know Blender.");
  await expect(page.getByRole("link", { name: "Start a project" })).toBeVisible();
  // One WebGL context on the page: the hero viewer.
  await expect(page.locator("canvas")).toHaveCount(1);
});

test("pricing: choosing a plan bumps the sidebar credits", async ({ page }) => {
  await page.goto("/pricing");
  const credits = page.getByRole("link", { name: /credits\. Buy more$/ });
  await expect(credits).toHaveText(/^100 credits$/, { timeout: 10_000 });

  await page.getByRole("button", { name: "Choose plan: Creator" }).click();
  await expect(page.getByRole("status").getByText("Added 500 credits (prototype)")).toBeVisible();
  // The number ticks up over the slow motion duration; the final value is 100 + 500.
  await expect(credits).toHaveText(/^600 credits$/, { timeout: 10_000 });
});
