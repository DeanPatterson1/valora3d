import { test, expect } from "./fixtures";
import { signInAsGuest } from "./helpers";

test("sign up lands on /projects; the sidebar shows the account", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  await page.goto("/signup");
  await page.getByLabel("Name").fill("Ada Lovelace");
  await page.getByLabel("Email address").fill("ada@example.com");
  await page.getByRole("textbox", { name: "Password" }).fill("longenough");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByRole("button", { name: "Ada Lovelace" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("login reveals the password after a valid email and rejects an unknown account", async ({ page }) => {
  await page.goto("/login");
  const password = page.getByRole("textbox", { name: "Password" });
  await expect(password).toHaveCount(0);
  await page.getByLabel("Email address").fill("nobody@example.com");
  await expect(password).toBeVisible();
  await password.fill("longenough");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("No account with that email").first()).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("settings → log out → /login, and the app is gated again", async ({ page }) => {
  await signInAsGuest(page, "/settings");
  await page.getByRole("button", { name: "Account", exact: true }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/login\?next=%2Fsettings$/);
});

test("delete all data asks first, then signs out", async ({ page }) => {
  await signInAsGuest(page, "/settings");
  await page.getByRole("button", { name: "Data controls", exact: true }).click();
  await page.getByRole("button", { name: "Delete all", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Delete all data" }).click();
  await expect(page).toHaveURL(/\/login$/);
  // The guest account itself is gone; a fresh guest is created on the next visit.
  expect(await page.evaluate(() => localStorage.getItem("rs.users"))).toBeNull();
});

test("sidebar user menu reaches profile with real counts; a guest gets a sign-in link", async ({ page }) => {
  await signInAsGuest(page);
  await expect(page.getByRole("link", { name: /Guest/ })).toHaveAttribute("href", "/login");

  await page.goto("/signup");
  await page.getByLabel("Name").fill("Ada Lovelace");
  await page.getByLabel("Email address").fill("ada@example.com");
  await page.getByRole("textbox", { name: "Password" }).fill("longenough");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByRole("button", { name: /new project/i }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: /^create$/i }).click();
  await expect(page).toHaveURL(/\/projects\/[^/?]+$/);

  await page.getByRole("button", { name: "Ada Lovelace" }).click();
  const menu = page.getByRole("menu", { name: "Account" });
  await expect(menu).toBeVisible();
  await menu.getByRole("menuitem", { name: "Profile" }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.getByRole("heading", { name: "Ada Lovelace" })).toBeVisible();
  const usage = page.getByRole("group", { name: "Usage" });
  await expect(usage.getByText("Projects").locator("xpath=preceding-sibling::span")).toHaveText("1");
  await expect(page.getByRole("main").getByRole("link", { name: /Untitled project/ })).toBeVisible();
});

test("an email link waits for a click on /auth/continue and warns in a browser that did not ask for it", async ({ page }) => {
  const hash = "pkce_0123456789abcdef0123456789abcdef";
  await page.goto(`/auth/continue?token_hash=${hash}&type=email&next=/projects`);
  await expect(page.getByRole("heading", { name: "Confirm your email" })).toBeVisible();
  await expect(page.getByRole("note")).toContainText("different browser");
  await expect(page.locator('form[action="/auth/confirm"][method="post"] input[name="token_hash"]')).toHaveValue(hash);
  // A browser that asked for the email (sign-up / reset set this cookie) gets no warning.
  await page.context().addCookies([{ name: "v3d_email_flow", value: "1", url: page.url() }]);
  await page.reload();
  await expect(page.getByRole("note")).toHaveCount(0);
  // Bad links never render the form.
  await page.goto(`/auth/continue?token_hash=${hash}&type=magiclink`);
  await expect(page.getByRole("heading", { name: "Link expired" })).toBeVisible();
});
