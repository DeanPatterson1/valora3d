import { test, expect } from "./fixtures";
import { signInAsGuest } from "./helpers";

// Pricing value lines, the Profile invite card, the examples pages and the free .glb checker (pricing lane).

test("pricing states what the credits buy, and Free is never promised a Final", async ({ page }) => {
  await page.goto("/pricing");
  const plans = page.getByRole("list", { name: "Plans", exact: true });
  await expect(plans.getByTestId("plan-value")).toHaveText([
    "10 credits = 2 Previews",
    "800 credits a month = 160 Previews or 8 Finals",
    "2,500 credits a month = 500 Previews or 25 Finals",
  ]);
  const packs = page.getByRole("list", { name: "Credit packs" });
  await expect(packs.getByRole("listitem")).toHaveCount(4);
  for (const price of ["$2", "$6", "$20", "$55"]) await expect(packs.getByText(price, { exact: true })).toBeVisible();
  await expect(packs.getByText("One per account.")).toHaveCount(1);
  await expect(page.getByText("$24", { exact: true })).toBeVisible();
});

test("Profile shows the invite card with a copyable referral link", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await signInAsGuest(page, "/profile");
  const card = page.getByRole("region", { name: "Invite friends" });
  await expect(card).toBeVisible();
  const link = card.getByRole("textbox", { name: "Your invite link" });
  await expect(link).toHaveValue(/\/signup\?ref=u_[a-z0-9]{10}$/);
  await card.getByRole("button", { name: "Copy link" }).click();
  await expect(page.getByRole("status").getByText("Invite link copied")).toBeVisible();
  await expect(card.getByText(/you both get 100 credits/)).toBeVisible();
  await expect(card.getByRole("link", { name: "Referral terms" })).toHaveAttribute("href", "/terms#referrals");
});

test("the referral link carries its ref into first-touch attribution", async ({ page, context }) => {
  await page.goto("/signup?ref=u_abc123def4");
  const cookie = (await context.cookies()).find((c) => c.name === "v3d_src");
  expect(cookie).toBeDefined();
  const decoded = JSON.parse(Buffer.from(cookie!.value.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8"));
  expect(decoded.ref).toBe("u_abc123def4");
});

test("examples index lists every clip and a detail page plays one with its structured data", async ({ page }) => {
  await page.goto("/examples");
  const first = page.locator('main a[href^="/examples/"]').first();
  const href = await first.getAttribute("href");
  expect(href).toBeTruthy();
  await page.goto(href!);
  await expect(page.locator("video")).toHaveCount(1);
  const ld = await page.locator('script[type="application/ld+json"]').allTextContents();
  expect(ld.some((t) => t.includes('"VideoObject"'))).toBe(true);
});

test("the glb checker reads the sample locally and gives a verdict", async ({ page }) => {
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.method() !== "GET") posts.push(r.url());
  });
  await page.goto("/tools/glb-checker");
  await page.getByRole("button", { name: "Try with a sample" }).click();
  await expect(page.getByRole("heading", { name: /Ready for Valora3D\?/ })).toBeVisible({ timeout: 60_000 });
  // Nothing is uploaded: no request other than GETs (the page, its chunks and the sample itself).
  expect(posts.filter((u) => !u.includes("/api/events") && !u.includes("/api/client-errors"))).toEqual([]);
});
