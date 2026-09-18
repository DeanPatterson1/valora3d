import { test, expect } from "@playwright/test";

test("landing: headline, nav after scrolling past the hero, CTA into the app", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("You don't need to know Blender.");
  await expect(page.getByText("Prototype · renderer not connected yet")).toBeVisible();
  // No WebGL on the landing: the hero is a captured video, not a live viewer.
  await expect(page.locator("canvas")).toHaveCount(0);

  // The pill nav is hidden over the hero and appears once the sheet has scrolled over it.
  const nav = page.getByRole("navigation", { name: "Landing" });
  await expect(nav).toHaveCSS("opacity", "0");
  await page.mouse.wheel(0, 2000);
  await expect(nav).toHaveAttribute("data-visible", "true");
  await expect(nav).toHaveCSS("opacity", "1");
  await expect(page.getByRole("heading", { level: 2, name: /Reviews · placeholder/ })).toBeAttached();

  await nav.getByRole("link", { name: "Start a project" }).click();
  await expect(page).toHaveURL(/\/projects\?new=1$/);
  expect(errors).toEqual([]);
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
