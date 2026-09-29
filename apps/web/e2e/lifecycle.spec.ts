import { expect, test, type Page } from "@playwright/test";
import { signInAsGuest } from "./helpers";

/**
 * Lifecycle surfaces in Local mode: notification settings, the feedback dialog, the cancel flow and past-due banner
 * (fixtures on /dev/lifecycle), the admin Feedback screen (fixtures on /dev/admin/feedback) and the unsubscribe page.
 * SHOTS_DIR=<dir> also saves desktop + phone screenshots of each.
 */
const SHOTS = process.env.SHOTS_DIR;

async function shoot(page: Page, name: string) {
  if (!SHOTS) return;
  // Let dialog fade-ins finish.
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}/lifecycle-${name}-desktop.png` });
  const size = page.viewportSize();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}/lifecycle-${name}-phone.png` });
  if (size) await page.setViewportSize(size);
}

test.use({ viewport: { width: 1440, height: 900 } });

test("notification settings: renders and tips are separate switches, account mail is always on", async ({ page }) => {
  await signInAsGuest(page, "/settings?section=notifications");
  const renders = page.getByRole("switch", { name: "Email me about my renders" });
  const tips = page.getByRole("switch", { name: "Email me product tips" });
  await expect(renders).toHaveAttribute("aria-checked", "true");
  await expect(tips).toHaveAttribute("aria-checked", "true");
  await expect(page.getByText("Always on")).toBeVisible();
  await shoot(page, "settings-notifications");
  await tips.click();
  await expect(tips).toHaveAttribute("aria-checked", "false");
  await page.reload();
  await expect(page.getByRole("switch", { name: "Email me product tips" })).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("switch", { name: "Email me about my renders" })).toHaveAttribute("aria-checked", "true");
});

test("feedback opens from the sidebar and from an error link", async ({ page }) => {
  await signInAsGuest(page, "/projects");
  await page.getByRole("button", { name: "Feedback" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Send feedback" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/We'll attach the page \(\/projects\)/)).toBeVisible();
  // Local mode has no server: the dialog offers email instead.
  await dialog.getByLabel("Message").fill("The render button did nothing.");
  await expect(dialog.getByRole("link", { name: "Email it" })).toHaveAttribute("href", /^mailto:support@valora3d\.com/);
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toBeHidden();

  await page.goto("/projects?feedback=bug&from=/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f");
  await expect(page.getByRole("dialog", { name: "Send feedback" }).getByText(/\/projects\/\[id\]/)).toBeVisible();
});

test("feedback dialog (server mode preview)", async ({ page }) => {
  test.skip(process.env.E2E_PRODUCTION === "1", "uses /dev fixtures, which 404 in production");
  await signInAsGuest(page, "/projects");
  await page.goto("/dev/lifecycle?view=feedback");
  const dialog = page.getByRole("dialog", { name: "Send feedback" });
  await dialog.getByLabel("Message").fill("The Render button stayed grey after I picked Final 1080p.");
  await shoot(page, "feedback-dialog");
  await dialog.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Thanks. We'll look into it.")).toBeVisible();
});

test("cancel flow: reason, offers, confirmation", async ({ page }) => {
  test.skip(process.env.E2E_PRODUCTION === "1", "uses /dev fixtures, which 404 in production");
  await signInAsGuest(page, "/projects");
  await page.goto("/dev/lifecycle?view=cancel-reason");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Cancel Pro?" })).toBeVisible();
  await dialog.getByText("It's too expensive").click();
  await shoot(page, "cancel-1-reason");
  await dialog.getByRole("button", { name: "Continue" }).click();
  await expect(dialog.getByRole("heading", { name: "Before you go" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Switch to Creator" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Pause instead" })).toBeVisible();
  await shoot(page, "cancel-2-offer");
  await dialog.getByRole("button", { name: "Cancel at period end" }).click();
  await expect(dialog.getByRole("heading", { name: "Your plan will end" })).toBeVisible();
  await shoot(page, "cancel-3-done");
});

test("past-due banner", async ({ page }) => {
  test.skip(process.env.E2E_PRODUCTION === "1", "uses /dev fixtures, which 404 in production");
  await signInAsGuest(page, "/projects");
  await page.goto("/dev/lifecycle?view=past-due");
  const banner = page.getByRole("status").filter({ hasText: "didn't go through" });
  await expect(banner).toBeVisible();
  await expect(banner.getByRole("button", { name: "Update payment method" })).toBeVisible();
  await shoot(page, "past-due-banner");
});

test("admin feedback screen (fixtures)", async ({ page }) => {
  test.skip(process.env.E2E_PRODUCTION === "1", "uses /dev fixtures, which 404 in production");
  await signInAsGuest(page, "/projects");
  await page.goto("/dev/admin/feedback");
  await expect(page.getByRole("heading", { name: "Feedback", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Why people cancel" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Suppressed addresses" }).getByText("angry@example.org")).toBeVisible();
  await shoot(page, "admin-feedback");
  await page.getByRole("tab", { name: "New" }).click();
  await expect(page.getByText("Would love a turntable preset")).toBeHidden();
});

test("unsubscribe page: an incomplete link explains itself, a full one asks to confirm", async ({ page }) => {
  await page.goto("/unsubscribe");
  await expect(page.getByRole("heading", { name: "This link doesn't work" })).toBeVisible();
  await page.goto("/unsubscribe?u=3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f&c=tips&t=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");
  await expect(page.getByRole("heading", { name: "Unsubscribe from product tips?" })).toBeVisible();
  await shoot(page, "unsubscribe");
  await page.goto("/unsubscribe?done=renders");
  await expect(page.getByRole("heading", { name: "You're unsubscribed" })).toBeVisible();
});
