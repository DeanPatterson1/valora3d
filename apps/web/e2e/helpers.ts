import type { Page } from "@playwright/test";

/** Signs in as the guest user so gated routes render. Lands on `next`. */
export async function signInAsGuest(page: Page, next = "/projects") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await page.waitForURL((url) => url.pathname === next.split("?")[0]);
}
