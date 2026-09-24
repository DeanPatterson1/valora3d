import { test, expect } from "@playwright/test";
import { signInAsGuest } from "./helpers";

test("phone navigation contains keyboard focus and returns to the trigger", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsGuest(page);
  const trigger = page.getByRole("button", { name: "Open sidebar", exact: true });
  await trigger.click();
  const drawer = page.getByRole("dialog", { name: "Navigation" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("link", { name: "Valora3D", exact: true })).toBeFocused();
  await expect(drawer.getByRole("link", { name: "All projects", exact: true })).toBeVisible();
  await expect(drawer.getByRole("link", { name: "Settings", exact: true })).toBeVisible();
  for (let i = 0; i < 15; i++) {
    await page.keyboard.press("Tab");
    expect(await drawer.evaluate(el => el.contains(document.activeElement))).toBe(true);
  }
  for (let i = 0; i < 15; i++) {
    await page.keyboard.press("Shift+Tab");
    expect(await drawer.evaluate(el => el.contains(document.activeElement))).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await drawer.getByRole("link", { name: "Settings", exact: true }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(drawer).not.toBeVisible();
});

test("phone settings expose every section and fit their controls", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsGuest(page, "/settings");
  const nav = page.getByRole("navigation", { name: "Settings sections" });
  await expect(nav.getByRole("button", { name: "Account", exact: true })).toBeInViewport();
  await nav.getByRole("button", { name: "Rendering", exact: true }).click();
  const group = page.getByRole("radiogroup", { name: "Default quality" });
  const bounds = await group.boundingBox();
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390);
  await group.getByRole("radio", { name: "Ultra" }).click();
  await expect(group.getByRole("radio", { name: "Ultra" })).toHaveAttribute("aria-checked", "true");
});
