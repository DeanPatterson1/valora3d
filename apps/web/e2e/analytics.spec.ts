import { expect, test } from "./fixtures";

// First-party analytics in Local mode: the tracker, the attribution cookie and the report endpoints. Local mode stores
// nothing, so these check what the browser sends and what the server accepts.

test("landing view goes to /api/events with a tab session id and a route template", async ({ page }) => {
  const sent = page.waitForRequest((r) => r.url().endsWith("/api/events") && r.method() === "POST");
  await page.goto("/");
  const req = await sent;
  const body = JSON.parse(req.postData() ?? "{}");
  expect(body.session_id).toMatch(/^[A-Za-z0-9_-]{16,64}$/);
  expect(body.events).toContainEqual({ event: "landing_view", props: {}, path: "/" });
  expect(await page.evaluate(() => sessionStorage.getItem("v3d_sid"))).toBe(body.session_id);
  expect((await page.context().cookies()).map((c) => c.name)).not.toContain("v3d_sid");
});

test("a campaign visit sets the first-touch cookie once; a direct visit sets none", async ({ page, context }) => {
  await page.goto("/pricing");
  expect((await context.cookies()).find((c) => c.name === "v3d_src")).toBeUndefined();
  await page.goto("/pricing?utm_source=Newsletter&utm_campaign=launch");
  const first = (await context.cookies()).find((c) => c.name === "v3d_src");
  expect(first).toBeTruthy();
  expect(first).toMatchObject({ httpOnly: true, sameSite: "Lax" });
  expect(first!.expires - Date.now() / 1000).toBeGreaterThan(89 * 86400);
  const decoded = JSON.parse(Buffer.from(first!.value, "base64url").toString());
  expect(decoded).toMatchObject({ source: "newsletter", campaign: "launch", landing: "/pricing" });
  await page.goto("/?utm_source=other");
  expect((await context.cookies()).find((c) => c.name === "v3d_src")?.value).toBe(first!.value);
});

test.describe("with Global Privacy Control", () => {
  test.use({ extraHTTPHeaders: { "Sec-GPC": "1" } });
  test("no attribution cookie is set", async ({ page, context }) => {
    await page.goto("/?utm_source=newsletter");
    expect((await context.cookies()).find((c) => c.name === "v3d_src")).toBeUndefined();
  });
});

test("report endpoints accept fixed fields only; flags read all on in Local mode", async ({ page, baseURL }) => {
  await page.goto("/pricing");
  const headers = { origin: baseURL!, "content-type": "application/json" };
  const ok = await page.request.post("/api/client-errors", {
    headers,
    data: { kind: "global", path: "/pricing", name: "TypeError", release: "dev" },
  });
  expect(ok.status()).toBe(204);
  const freeText = await page.request.post("/api/client-errors", {
    headers,
    data: { kind: "global", path: "/", name: "TypeError", release: "dev", message: "user@example.com" },
  });
  expect(freeText.status()).toBe(400);
  const serverEvent = await page.request.post("/api/events", {
    headers,
    data: { session_id: "abcdefghijklmnop_1", events: [{ event: "checkout_complete" }] },
  });
  expect(serverEvent.status()).toBe(400);
  const flags = await (await page.request.get("/api/flags")).json();
  expect(flags.flags).toEqual({ renders_enabled: true, finals_enabled: true, signups_enabled: true, sharing_enabled: true, checkout_enabled: true });
});
