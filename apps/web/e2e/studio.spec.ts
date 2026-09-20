import { test, expect } from "@playwright/test";
import { signInAsGuest } from "./helpers";

/**
 * The whole studio flow in one browser session: new project, sample model, first
 * scene, an edit, then the render surfaces. State lives in IndexedDB, so each
 * test gets a fresh context and therefore a fresh database.
 */
test("create project, load sample, plan, edit, reach the render surfaces", async ({ page }) => {
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

  // Scene details → Render tab. Local rendering needs the Blender server, which this
  // run does not assume; cloud is deterministically not connected, so assert that.
  await page.getByRole("button", { name: "Scene details" }).click();
  await page.getByRole("tab", { name: "Render" }).click();
  await page.getByRole("button", { name: /Local GPU|Cloud GPU/ }).click();
  await page.getByRole("radio", { name: /Cloud GPU/ }).click();
  await page.getByTestId("render-final").click();
  await expect(page.getByTestId("render-not-connected")).toBeVisible();
});

test("separate and delete geometry, and keep it across a reload", async ({ page }) => {
  await signInAsGuest(page);
  await page.getByRole("button", { name: /new project/i }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: /^create$/i }).click();
  await expect(page).toHaveURL(/\/projects\/[^/?]+$/);

  await page.getByRole("button", { name: "Model options" }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Add a model" }).click();
  await chooser;
  await page.getByRole("button", { name: "Sample car" }).click();
  await expect(page.locator("[data-model-loaded='true']")).toBeVisible({ timeout: 60_000 });

  // The Model tab opens with the model, before any prompt has been sent.
  await page.getByRole("button", { name: "Scene details" }).click();
  await page.getByRole("tab", { name: "Model" }).click();
  const rows = page.getByTestId("outliner-row");
  await expect(rows.first()).toBeVisible();
  const before = await rows.count();

  // Deleting a group takes its whole subtree out of the outliner.
  await rows.first().click();
  await page.getByTestId("delete-parts").click();
  await expect.poll(() => rows.count()).toBeLessThan(before);
  const after = await rows.count();

  // Edits are keyed by a stable node path, so they replay on the next load.
  await page.reload();
  await expect(page.locator("[data-model-loaded='true']")).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Scene details" }).click();
  await page.getByRole("tab", { name: "Model" }).click();
  await expect(page.getByTestId("outliner-row")).toHaveCount(after);
});
