import { expect, test } from "@playwright/test";
import { signInAsGuest } from "./helpers";

test("profile Usage & billing shows the plan, balance and credit history", async ({ page }) => {
  await signInAsGuest(page, "/profile?tab=billing");
  await expect(page.getByRole("tab", { name: "Usage & billing" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("One-time credits, no renewal.")).toBeVisible();
  const table = page.getByRole("table");
  await expect(table.getByText("Starting credits")).toBeVisible();
  await expect(page.getByText(/No renders yet/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Get credits" })).toHaveAttribute("href", "/pricing");
});

test("settings deep link turns render-ready emails off and it sticks", async ({ page }) => {
  await signInAsGuest(page, "/settings?section=notifications");
  const sw = page.getByRole("switch", { name: "Email me about my renders" });
  await expect(sw).toHaveAttribute("aria-checked", "true");
  await sw.click();
  await expect(sw).toHaveAttribute("aria-checked", "false");
  await page.reload();
  await expect(page.getByRole("switch", { name: "Email me about my renders" })).toHaveAttribute("aria-checked", "false");
});
