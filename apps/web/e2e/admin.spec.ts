import { test, expect } from "./fixtures";
import { signInAsGuest } from "./helpers";

/**
 * The owner console in Local mode (no Supabase): /admin explains it needs the live backend, and every admin API
 * route refuses. The populated screens are exercised on /dev/admin (sample data, dev only).
 */

const JOB = "9c3a5d02-0000-4000-8000-000000000002";
const USER = "3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f";

test("/admin in Local mode: a notice, never indexed", async ({ page }) => {
  const res = await page.goto("/admin");
  expect(res?.status()).toBe(200);
  expect(res?.headers()["x-robots-tag"]).toBe("noindex, nofollow");
  await expect(page.getByRole("heading", { name: "Admin requires the live backend" })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  await expect(page.getByRole("navigation", { name: "Admin" })).toHaveCount(0);
  const sub = await page.goto("/admin/users");
  expect(sub?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Admin requires the live backend" })).toBeVisible();
});

test("every admin API route answers 403 without an admin session", async ({ request, baseURL }) => {
  const origin = { origin: baseURL ?? "" };
  const gets = ["overview", "renders", `renders/${JOB}`, "users?q=a", `users/${USER}`, "billing", "audit"];
  for (const path of gets) {
    const res = await request.get(`/api/admin/${path}`);
    expect(res.status(), path).toBe(403);
    expect(res.headers()["x-robots-tag"], path).toBe("noindex, nofollow");
  }
  const posts: [string, unknown][] = [
    [`renders/${JOB}/retry`, {}],
    [`renders/${JOB}/refund`, { reason: "test", request_id: "req12345678" }],
    [`users/${USER}/credits`, { amount: 100, reason: "test", request_id: "req12345678" }],
  ];
  for (const [path, data] of posts) {
    const res = await request.post(`/api/admin/${path}`, { data, headers: origin });
    expect(res.status(), path).toBe(403);
  }
});

test("admin screens with sample data: overview, renders, job, users, user, billing, audit", async ({ page }) => {
  test.skip(process.env.E2E_PRODUCTION === "1", "uses /dev/admin, which 404s in production");
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await signInAsGuest(page, "/dev/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  await page.getByRole("tab", { name: "30 days" }).click();
  await expect(page.getByText("Gross, USD")).toBeVisible();

  await nav.getByRole("link", { name: "Renders" }).click();
  await expect(page.getByRole("table", { name: "Render jobs" })).toBeVisible();
  await page.getByLabel("Status").selectOption("failed");
  await expect(page.getByRole("table", { name: "Render jobs" }).locator("tbody tr")).toHaveCount(2);
  await page.getByRole("link", { name: JOB.slice(0, 8) }).click();
  await expect(page.getByRole("heading", { name: `Job ${JOB.slice(0, 8)}` })).toBeVisible();
  await expect(page.getByText("GPU_OOM").first()).toBeVisible();
  await page.getByRole("button", { name: "Retry render" }).click();
  await page.getByRole("button", { name: "Retry now" }).click();
  await expect(page.getByText("Preview only: nothing was changed.")).toBeVisible();

  await nav.getByRole("link", { name: "Users" }).click();
  await expect(page.getByRole("table", { name: "Users" })).toBeVisible();
  await page.getByRole("link", { name: "jon@carsandcoffee.example" }).click();
  await expect(page.getByRole("heading", { name: "jon@carsandcoffee.example" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Credit ledger" })).toBeVisible();

  await nav.getByRole("link", { name: "Billing" }).click();
  await expect(page.getByRole("table", { name: "Webhook errors" })).toBeVisible();
  await nav.getByRole("link", { name: "Growth" }).click();
  await expect(page.getByRole("heading", { name: "Growth" })).toBeVisible();
  await expect(page.getByText("Weekly delivered renders")).toBeVisible();
  await nav.getByRole("link", { name: "Errors" }).click();
  await expect(page.getByRole("heading", { name: "Client errors" })).toBeVisible();
  await nav.getByRole("link", { name: "Flags" }).click();
  await expect(page.getByText("renders_enabled", { exact: true })).toBeVisible();
  await nav.getByRole("link", { name: "Audit" }).click();
  await expect(page.getByRole("table", { name: "Admin audit log" }).locator("tbody tr")).toHaveCount(4);
  expect(errors).toEqual([]);
});
