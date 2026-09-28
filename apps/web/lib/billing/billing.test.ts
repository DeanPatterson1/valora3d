import { describe, expect, it, vi } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { readBillingConfig, readPaddleEnvironment, type BillingConfig } from "@/lib/env";
import { CHECKOUT_ITEMS, PLAN_LIMITS, planCredits } from "@/lib/pricing";
import { buildCatalog, isCheckoutItem } from "./catalog";
import { parseWebhookEvent, signedUserId } from "./events";
import { createPaddleApi, paddleApiBase } from "./paddle-api";
import { parseSignatureHeader, signPaddlePayload, signUserId, verifyPaddleSignature } from "./signature";
import { handleWebhook, type ApplyArgs } from "./webhook";

// A test-only secret; never a real one.
const SECRET = "pdl_ntfset_test_secret_for_unit_tests_only";
const USER = "11111111-2222-4333-8444-555555555555";
const PRICES = {
  "plan:creator": "pri_creator",
  "plan:pro": "pri_pro",
  "pack:100": "pri_pack100",
  "pack:500": "pri_pack500",
  "pack:2000": "pri_pack2000",
} as const;
const catalog = buildCatalog(PRICES);
const NOW = Date.UTC(2026, 8, 28, 12, 0, 0);
const TS = Math.floor(NOW / 1000);

describe("verifyPaddleSignature", () => {
  const body = '{"event_id":"evt_1","event_type":"transaction.completed","data":{}}';

  it("accepts a valid signature", async () => {
    const header = await signPaddlePayload(body, SECRET, TS);
    expect(header).toMatch(/^ts=\d+;h1=[0-9a-f]{64}$/);
    expect(await verifyPaddleSignature(body, header, SECRET, NOW)).toEqual({ ok: true });
  });

  it("rejects a tampered body, a wrong secret and a forged h1", async () => {
    const header = await signPaddlePayload(body, SECRET, TS);
    expect(await verifyPaddleSignature(body.replace("evt_1", "evt_2"), header, SECRET, NOW)).toEqual({ ok: false, reason: "mismatch" });
    expect(await verifyPaddleSignature(body, header, "another-secret", NOW)).toEqual({ ok: false, reason: "mismatch" });
    expect(await verifyPaddleSignature(body, `ts=${TS};h1=${"0".repeat(64)}`, SECRET, NOW)).toEqual({ ok: false, reason: "mismatch" });
    expect(await verifyPaddleSignature(body, `ts=${TS};h1=nothex`, SECRET, NOW)).toEqual({ ok: false, reason: "mismatch" });
  });

  it("rejects a stale or future timestamp (replay window 5 min)", async () => {
    const old = await signPaddlePayload(body, SECRET, TS - 301);
    expect(await verifyPaddleSignature(body, old, SECRET, NOW)).toEqual({ ok: false, reason: "stale" });
    const future = await signPaddlePayload(body, SECRET, TS + 301);
    expect(await verifyPaddleSignature(body, future, SECRET, NOW)).toEqual({ ok: false, reason: "stale" });
    const recent = await signPaddlePayload(body, SECRET, TS - 299);
    expect(await verifyPaddleSignature(body, recent, SECRET, NOW)).toEqual({ ok: true });
  });

  it("rejects a missing or malformed header", async () => {
    expect(await verifyPaddleSignature(body, null, SECRET, NOW)).toEqual({ ok: false, reason: "missing" });
    expect(await verifyPaddleSignature(body, "garbage", SECRET, NOW)).toEqual({ ok: false, reason: "malformed" });
    expect(await verifyPaddleSignature(body, `ts=${TS}`, SECRET, NOW)).toEqual({ ok: false, reason: "malformed" });
  });

  it("accepts any matching h1 (secret rotation)", async () => {
    const good = (await signPaddlePayload(body, SECRET, TS)).split("h1=")[1];
    const header = `ts=${TS};h1=${"a".repeat(64)};h1=${good}`;
    expect(parseSignatureHeader(header)?.h1).toHaveLength(2);
    expect(await verifyPaddleSignature(body, header, SECRET, NOW)).toEqual({ ok: true });
  });
});

describe("catalog", () => {
  it("maps each checkout item to its price and credits, and back", () => {
    expect(catalog.byItem("plan:creator")).toEqual({ item: "plan:creator", priceId: "pri_creator", kind: "plan", plan: "creator", credits: 500 });
    expect(catalog.byItem("plan:pro")?.credits).toBe(2000);
    expect(catalog.byItem("pack:500")).toEqual({ item: "pack:500", priceId: "pri_pack500", kind: "pack", credits: 500 });
    expect(catalog.byPriceId("pri_pack2000")?.credits).toBe(2000);
    expect(catalog.byPriceId("pri_unknown")).toBeNull();
    expect(catalog.byItem("pack:999")).toBeNull();
  });

  it("only knows the fixed checkout items; the browser cannot name a price or amount", () => {
    expect(CHECKOUT_ITEMS).toEqual(["plan:creator", "plan:pro", "pack:100", "pack:500", "pack:2000"]);
    expect(isCheckoutItem("pack:100")).toBe(true);
    expect(isCheckoutItem("pri_pack100")).toBe(false);
    expect(isCheckoutItem({ amount: 1 })).toBe(false);
  });

  it("leaves unconfigured items off sale and refuses one price on two items", () => {
    expect(buildCatalog({ "pack:100": "pri_a" }).byItem("plan:pro")).toBeNull();
    expect(() => buildCatalog({ "pack:100": "pri_a", "pack:500": "pri_a" })).toThrow(/two items/);
  });

  it("reads prices from env and fails closed without a webhook secret", () => {
    expect(readBillingConfig({})).toBeNull();
    const cfg = readBillingConfig({
      PADDLE_WEBHOOK_SECRET: " s ",
      PADDLE_PRICE_PRO_MONTHLY: "pri_pro",
      PADDLE_PRICE_PACK_100: "not-a-price",
    });
    expect(cfg).toEqual({ environment: "sandbox", apiKey: null, webhookSecret: "s", prices: { "plan:pro": "pri_pro" } });
    expect(readPaddleEnvironment("production")).toBe("production");
    expect(readPaddleEnvironment("prod")).toBe("sandbox");
    expect(paddleApiBase("sandbox")).toBe("https://sandbox-api.paddle.com");
    expect(paddleApiBase("production")).toBe("https://api.paddle.com");
  });
});

// ---- event -> ledger action --------------------------------------------------------------

async function customData(userId = USER) {
  return { user_id: userId, user_sig: await signUserId(userId, SECRET) };
}

function envelope(eventType: string, data: Record<string, unknown>, eventId = "evt_01abc") {
  return JSON.stringify({ event_id: eventId, event_type: eventType, occurred_at: "2026-09-28T12:00:00Z", notification_id: "ntf_1", data });
}

const packTxn = async (overrides: Record<string, unknown> = {}) => ({
  id: "txn_pack1",
  status: "completed",
  origin: "web",
  customer_id: "ctm_abc",
  subscription_id: null,
  custom_data: await customData(),
  currency_code: "USD",
  items: [{ price: { id: "pri_pack500" }, quantity: 1 }],
  details: { totals: { total: "2000", grand_total: "2000" } },
  billing_period: null,
  ...overrides,
});

const subTxn = async (overrides: Record<string, unknown> = {}) => ({
  ...(await packTxn()),
  id: "txn_sub1",
  subscription_id: "sub_abc",
  items: [{ price: { id: "pri_creator" }, quantity: 1 }],
  billing_period: { starts_at: "2026-09-28T12:00:00Z", ends_at: "2026-10-28T12:00:00Z" },
  details: { totals: { grand_total: "1900" } },
  ...overrides,
});

describe("parseWebhookEvent", () => {
  it("a pack purchase becomes a credit grant keyed by the transaction id", async () => {
    const e = await parseWebhookEvent(envelope("transaction.completed", await packTxn()), catalog, SECRET);
    expect(e).toEqual({
      eventId: "evt_01abc",
      eventType: "transaction.completed",
      occurredAt: "2026-09-28T12:00:00Z",
      action: {
        kind: "grant_pack", user_id: USER, customer_id: "ctm_abc", transaction_id: "txn_pack1",
        credits: 500, total_minor: 2000, currency_code: "USD",
      },
    });
  });

  it("multiplies pack credits by quantity and ignores unknown prices", async () => {
    const e = await parseWebhookEvent(envelope("transaction.completed", await packTxn({
      items: [{ price: { id: "pri_pack100" }, quantity: 3 }, { price: { id: "pri_somethingelse" }, quantity: 1 }],
    })), catalog, SECRET);
    expect(e?.action).toMatchObject({ kind: "grant_pack", credits: 300 });
    const none = await parseWebhookEvent(envelope("transaction.completed", await packTxn({
      items: [{ price: { id: "pri_somethingelse" }, quantity: 1 }],
    })), catalog, SECRET);
    expect(none?.action).toEqual({ kind: "ignore", reason: "no catalog price in transaction" });
  });

  it("a subscription payment grants the plan credits for that billing period", async () => {
    const e = await parseWebhookEvent(envelope("transaction.completed", await subTxn()), catalog, SECRET);
    expect(e?.action).toEqual({
      kind: "grant_subscription", user_id: USER, customer_id: "ctm_abc", transaction_id: "txn_sub1",
      subscription_id: "sub_abc", plan: "creator", credits: 500,
      period_start: "2026-09-28T12:00:00Z", period_end: "2026-10-28T12:00:00Z", total_minor: 1900, currency_code: "USD",
    });
  });

  it("renewals (no custom data needed) and upgrades grant; other subscription charges do not", async () => {
    const renewal = await parseWebhookEvent(envelope("transaction.completed", await subTxn({ origin: "subscription_recurring", custom_data: null })), catalog, SECRET);
    expect(renewal?.action).toMatchObject({ kind: "grant_subscription", user_id: null, subscription_id: "sub_abc" });
    const upgrade = await parseWebhookEvent(envelope("transaction.completed", await subTxn({
      origin: "subscription_update", items: [{ price: { id: "pri_pro" }, quantity: 1 }],
    })), catalog, SECRET);
    expect(upgrade?.action).toMatchObject({ kind: "grant_subscription", plan: "pro", credits: 2000 });
    const trial = await parseWebhookEvent(envelope("transaction.completed", await subTxn({ details: { totals: { grand_total: "0" } } })), catalog, SECRET);
    expect(trial?.action).toEqual({ kind: "ignore", reason: "unpaid first period" });
    const methodChange = await parseWebhookEvent(envelope("transaction.completed", await subTxn({ origin: "subscription_payment_method_change" })), catalog, SECRET);
    expect(methodChange?.action.kind).toBe("ignore");
  });

  it("does not trust an unsigned or forged user id", async () => {
    const forged = { user_id: "99999999-2222-4333-8444-555555555555", user_sig: (await customData()).user_sig };
    const e = await parseWebhookEvent(envelope("transaction.completed", await packTxn({ custom_data: forged })), catalog, SECRET);
    expect(e?.action).toMatchObject({ kind: "grant_pack", user_id: null });
    expect(await signedUserId({ user_id: USER }, SECRET)).toBeNull();
    expect(await signedUserId({ user_id: "not-a-uuid", user_sig: "x" }, SECRET)).toBeNull();
    expect(await signedUserId(await customData(), "other-secret")).toBeNull();
  });

  it("subscription events carry status, plan and period; unknown plans are ignored", async () => {
    const sub = {
      id: "sub_abc", status: "canceled", customer_id: "ctm_abc", custom_data: await customData(),
      items: [{ price: { id: "pri_pro" }, quantity: 1 }],
      current_billing_period: null, scheduled_change: null,
      canceled_at: "2026-10-28T12:00:00Z", updated_at: "2026-10-28T12:00:01Z",
    };
    const e = await parseWebhookEvent(envelope("subscription.canceled", sub), catalog, SECRET);
    expect(e?.action).toEqual({
      kind: "subscription_state", user_id: USER, customer_id: "ctm_abc", subscription_id: "sub_abc",
      plan: "pro", price_id: "pri_pro", status: "canceled", period_start: null, period_end: null,
      scheduled_change: null, canceled_at: "2026-10-28T12:00:00Z", updated_at: "2026-10-28T12:00:01Z",
    });
    const pastDue = await parseWebhookEvent(envelope("subscription.past_due", { ...sub, status: "past_due" }), catalog, SECRET);
    expect(pastDue?.action).toMatchObject({ kind: "subscription_state", status: "past_due" });
    const unknown = await parseWebhookEvent(envelope("subscription.updated", { ...sub, items: [{ price: { id: "pri_x" } }] }), catalog, SECRET);
    expect(unknown?.action.kind).toBe("ignore");
  });

  it("approved refunds and chargebacks become reversals; pending ones wait", async () => {
    const adj = { id: "adj_1", action: "refund", status: "approved", type: "partial", transaction_id: "txn_pack1", totals: { total: "1000" } };
    expect((await parseWebhookEvent(envelope("adjustment.updated", adj), catalog, SECRET))?.action).toEqual({
      kind: "reversal", adjustment_id: "adj_1", transaction_id: "txn_pack1", action: "refund", full: false, amount_minor: 1000,
    });
    expect((await parseWebhookEvent(envelope("adjustment.created", { ...adj, status: "pending_approval" }), catalog, SECRET))?.action)
      .toEqual({ kind: "ignore", reason: "adjustment pending_approval" });
    expect((await parseWebhookEvent(envelope("adjustment.created", { ...adj, action: "chargeback", type: "full" }), catalog, SECRET))?.action)
      .toMatchObject({ kind: "reversal", action: "chargeback", full: true });
    expect((await parseWebhookEvent(envelope("adjustment.created", { ...adj, action: "credit" }), catalog, SECRET))?.action)
      .toMatchObject({ kind: "reversal", action: "credit" });
    expect((await parseWebhookEvent(envelope("adjustment.created", { ...adj, action: "chargeback_warning" }), catalog, SECRET))?.action.kind)
      .toBe("ignore");
  });

  it("other events are acknowledged and ignored; non-events are rejected", async () => {
    expect((await parseWebhookEvent(envelope("customer.created", { id: "ctm_1" }), catalog, SECRET))?.action)
      .toEqual({ kind: "ignore", reason: "event customer.created" });
    expect(await parseWebhookEvent("not json", catalog, SECRET)).toBeNull();
    expect(await parseWebhookEvent(JSON.stringify({ event_id: "nope", event_type: "x", data: {} }), catalog, SECRET)).toBeNull();
  });
});

// ---- the whole webhook, with an in-memory stand-in for billing_apply_event ------------------

/** Mirrors the SQL function's idempotency: an event id is applied once, a transaction ref once. */
function fakeDb() {
  const events = new Set<string>();
  const ledger = new Map<string, number>();
  const apply = vi.fn(async (args: ApplyArgs) => {
    if (events.has(args.p_event_id)) return { data: { outcome: "duplicate" }, error: null };
    events.add(args.p_event_id);
    const a = args.p_action;
    if (a.kind === "grant_pack") {
      const ref = `paddle:txn:${a.transaction_id}`;
      if (ledger.has(ref)) return { data: { outcome: "duplicate_txn" }, error: null };
      ledger.set(ref, a.credits);
      return { data: { outcome: "granted" }, error: null };
    }
    return { data: { outcome: a.kind === "ignore" ? "ignored" : "synced" }, error: null };
  });
  return { apply, ledger, events };
}

const billing: BillingConfig = { environment: "sandbox", apiKey: null, webhookSecret: SECRET, prices: PRICES };

async function paddleRequest(body: string, ts = TS, secret = SECRET) {
  return new Request("https://valora3d.com/api/billing/webhook", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Paddle-Signature": await signPaddlePayload(body, secret, ts) },
    body,
  });
}

describe("handleWebhook", () => {
  it("grants once however many times Paddle delivers the event", async () => {
    const db = fakeDb();
    const body = envelope("transaction.completed", await packTxn());
    const first = await handleWebhook(await paddleRequest(body), billing, db.apply, NOW);
    expect(first.status).toBe(200);
    expect(await first.json()).toEqual({ received: true, outcome: "granted" });
    const again = await handleWebhook(await paddleRequest(body), billing, db.apply, NOW);
    expect(await again.json()).toEqual({ received: true, outcome: "duplicate" });
    // The same transaction under a different event id is still one grant.
    const other = await handleWebhook(await paddleRequest(envelope("transaction.completed", await packTxn(), "evt_02abc")), billing, db.apply, NOW);
    expect(await other.json()).toEqual({ received: true, outcome: "duplicate_txn" });
    expect([...db.ledger]).toEqual([["paddle:txn:txn_pack1", 500]]);
  });

  it("refuses bad signatures and stale timestamps before touching the database", async () => {
    const db = fakeDb();
    const body = envelope("transaction.completed", await packTxn());
    expect((await handleWebhook(await paddleRequest(body, TS, "wrong"), billing, db.apply, NOW)).status).toBe(401);
    expect((await handleWebhook(await paddleRequest(body, TS - 3600), billing, db.apply, NOW)).status).toBe(401);
    const unsigned = new Request("https://valora3d.com/api/billing/webhook", { method: "POST", body });
    expect((await handleWebhook(unsigned, billing, db.apply, NOW)).status).toBe(401);
    expect(db.apply).not.toHaveBeenCalled();
  });

  it("returns 500 when the database fails, so Paddle retries", async () => {
    const apply = vi.fn(async () => ({ data: null, error: { code: "57014", message: "timeout" } }));
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const res = await handleWebhook(await paddleRequest(envelope("transaction.completed", await packTxn())), billing, apply, NOW);
    expect(res.status).toBe(500);
    spy.mockRestore();
  });

  it("rejects a signed body that is not a Paddle event", async () => {
    const db = fakeDb();
    expect((await handleWebhook(await paddleRequest("[]"), billing, db.apply, NOW)).status).toBe(400);
  });
});

describe("Paddle API client", () => {
  it("creates a portal session and returns the overview link", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ data: { urls: { general: { overview: "https://customer-portal.paddle.com/cpl_1?token=x" } } } }));
    const api = createPaddleApi("pdl_test_key", "sandbox", fetchImpl as unknown as typeof fetch);
    expect(await api.createPortalSession("ctm_abc", ["sub_abc"])).toEqual({ url: "https://customer-portal.paddle.com/cpl_1?token=x" });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://sandbox-api.paddle.com/customers/ctm_abc/portal-sessions");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer pdl_test_key");
    expect(JSON.parse(init.body as string)).toEqual({ subscription_ids: ["sub_abc"] });
  });

  it("reports Paddle errors", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ error: { code: "not_found" } }, { status: 404 }));
    const api = createPaddleApi("k", "production", fetchImpl as unknown as typeof fetch);
    expect(await api.createPortalSession("ctm_x", [])).toEqual({ error: "not_found" });
    expect(await api.changeSubscriptionPrice("sub_x", "pri_pro", "upgrade")).toEqual({ error: "not_found" });
  });

  it("charges upgrades pro rata and never refunds a downgrade", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ data: {} }));
    const api = createPaddleApi("k", "sandbox", fetchImpl as unknown as typeof fetch);
    await api.changeSubscriptionPrice("sub_x", "pri_pro", "upgrade");
    await api.changeSubscriptionPrice("sub_x", "pri_creator", "downgrade");
    const modes = fetchImpl.mock.calls.map((c) => JSON.parse((c as unknown as [string, RequestInit])[1].body as string).proration_billing_mode);
    expect(modes).toEqual(["prorated_immediately", "do_not_bill"]);
  });

  it("finds or creates the Paddle customer for an email, and lists live subscriptions", async () => {
    const found = vi.fn(async () => Response.json({ data: [{ id: "ctm_found" }] }));
    expect(await createPaddleApi("k", "sandbox", found as unknown as typeof fetch).customerForEmail("a@b.co")).toEqual({ id: "ctm_found" });
    expect((found.mock.calls[0] as unknown as [string])[0]).toBe("https://sandbox-api.paddle.com/customers?email=a%40b.co");
    const responses = [Response.json({ data: [] }), Response.json({ data: { id: "ctm_new" } }, { status: 201 })];
    const create = vi.fn(async () => responses.shift()!);
    expect(await createPaddleApi("k", "sandbox", create as unknown as typeof fetch).customerForEmail("a@b.co")).toEqual({ id: "ctm_new" });
    const list = vi.fn(async () => Response.json({ data: [{ id: "sub_1" }, { id: "sub_2" }] }));
    expect(await createPaddleApi("k", "sandbox", list as unknown as typeof fetch).listLiveSubscriptions("ctm_a")).toEqual({ ids: ["sub_1", "sub_2"] });
    expect((list.mock.calls[0] as unknown as [string])[0]).toContain("status=active,trialing,past_due,paused");
  });
});

describe("plan limits mirrored in the database", () => {
  const dir = join(__dirname, "..", "..", "supabase", "migrations");
  const sql = readdirSync(dir).filter((f) => f.endsWith(".sql")).map((f) => readFileSync(join(dir, f), "utf8")).join("\n");

  it("has the same limits per plan", () => {
    for (const [plan, l] of Object.entries(PLAN_LIMITS)) {
      const re = new RegExp(`\\('${plan}'::public\\.plan_tier,\\s*'([^']+)',\\s*(true|false),\\s*(\\d+),\\s*(\\d+)\\)`);
      const m = sql.match(re);
      expect(m, plan).not.toBeNull();
      expect([m![1], m![2] === "true", Number(m![3]), Number(m![4])]).toEqual([l.maxResolution, l.watermark, l.retentionDays, l.priority]);
    }
  });

  it("plan credits come from PLANS", () => {
    expect(planCredits("creator")).toBe(500);
    expect(planCredits("pro")).toBe(2000);
  });
});
