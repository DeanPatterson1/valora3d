import { test, expect } from "@playwright/test";
import { signInAsGuest } from "./helpers";

/**
 * The whole studio flow in one browser session: new project, sample model, first
 * scene, an edit, then the unavailable renderer. State lives in IndexedDB, so each
 * test gets a fresh context and therefore a fresh database.
 */
test("create project, load sample, plan, edit, render unavailable", async ({ page }) => {
  const cspErrors: string[] = [];
  page.on("console", (message) => {
    if (/content security policy|violates.*directive|refused to (load|connect|execute)/i.test(message.text())) cspErrors.push(message.text());
  });
  await signInAsGuest(page);

  // Dashboard → "New project" → dialog → "Create" → studio.
  await page.getByRole("button", { name: /new project/i }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: /^create$/i }).click();
  await expect(page).toHaveURL(/\/projects\/[^/?]+$/);

  // Without a model the `+` menu has one item that opens the file picker; the upload card keeps the samples.
  await page.getByRole("button", { name: "Model options" }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Add a model" }).click();
  await chooser;
  await page.getByRole("button", { name: "Sample car" }).click();
  await expect(page.locator("[data-model-loaded='true']")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("canvas")).toBeVisible();
  await expect(page.getByTestId("studio-status")).toContainText(/car/i, { timeout: 20_000 });

  // First scene. The status line and sidebar history advance once the labour sequence ends.
  const prompt = page.getByRole("textbox", { name: "Describe your render" });
  await prompt.fill("rainy night handheld walking toward the car");
  await page.keyboard.press("Enter");
  const history = page.getByRole("button", { name: /^1 version$/ });
  await expect(history).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("studio-status")).toHaveText("Scene ready · 1 version");
  await history.click();
  await expect(page.getByRole("listitem", { name: /^version 1:/i })).toBeVisible();

  // An edit appends a second version. `fill` waits for the textarea to come back after the sequence.
  await prompt.fill("darker");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /^2 versions$/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("listitem", { name: /^version 2: darker$/i })).toBeVisible();

  // Scene details → Render tab → Generate preview → the unavailable-render recovery state.
  await page.getByRole("button", { name: "Scene details" }).click();
  await page.getByRole("tab", { name: "Render" }).click();
  await page.getByRole("button", { name: /generate preview/i }).click();
  await expect(page.getByText(/rendering is currently unavailable/i)).toBeVisible();
  expect(cspErrors).toEqual([]);
});
