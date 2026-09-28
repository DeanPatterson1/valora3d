# Valora3D — web prototype

A frontend-only prototype of Valora3D (valora3d.com): upload a 3D model, describe the shot in plain words, and see the scene planned live in a WebGL viewer. The design follows the ChatGPT / Higgsfield language (neutral near-black surfaces, one white primary action, strict progressive disclosure).

## Run

```bash
npm install
npm run dev        # http://localhost:3000
npm run test       # vitest (jsdom)
npm run typecheck  # next typegen + tsc
npm run lint
npm run e2e        # Playwright (chromium, headless WebGL via swiftshader); reuses a running dev server
npm run build
```

First e2e run: `npx playwright install chromium`. Everything the studio spec loads is served locally: `/samples/car.glb` and the HDR environments under `public/hdri/` (`next/font` fetches Inter at build time). Reports land in `playwright-report/`, traces for failures in `test-results/` (both git-ignored).

## What is and is not here

- Without backend env, everything runs in the browser: projects, versions and credits persist in IndexedDB. With it, see "Backend" below.
- The **renderer is intentionally not connected**: "Render" surfaces are designed but produce no output. The footer and the local/cloud section say so.
- Services (storage, credits, planning) are swapped at one seam: `lib/services/index.ts`. Replace the local implementations there to talk to a real backend.

## Backend (Supabase + R2)

The service seam (`lib/services/index.ts`) picks the implementation at build time:

- **No `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`** → the in-browser `Local*` fakes (guest mode, demo providers, local ledger). `npm run dev`, vitest and Playwright use this; nothing needs a network.
- **Both set** → `Supabase*` services: real accounts (email + password with verification, Google, password reset, server-side account deletion), projects/versions in Postgres under RLS, the server credit ledger, and model files in R2. Guest mode and the demo providers are gone on this path.

Layout (Supabase CLI, run from `apps/web`): `supabase/config.toml` (local stack only), `supabase/migrations/*.sql` (schema, RLS, `create_render_job`, `refund_render_job`, `spend_credits`, new-user trigger granting `free_plan_credits()` = `FREE_PLAN_CREDITS` = 50), `supabase/tests/*.sql` (pgTAP: `supabase start && supabase test db`, local only).

Env: `.env.example` (for `next dev` / build) and `.dev.vars.example` (for `wrangler dev`). `NEXT_PUBLIC_*` are inlined at build time, so they must be set when `npm run cf:build` runs; `SUPABASE_SERVICE_ROLE_KEY` and `R2_*` are read at request time (`wrangler secret put`).

Server pieces: `proxy.ts` (session refresh; redirects signed-out visitors away from `/projects`, `/profile`, `/settings`, `/dev`), `app/api/uploads` (+ `/:id/complete`, `/:id/download`), `app/api/credits/spend`, `app/api/projects/:id` (DELETE), `app/api/account/delete`, `app/auth/callback` and `app/auth/confirm`. The service-role client is created only inside those routes, after `requireUser()`.

Uploads: `.glb` only, ≤ 200 MB. The browser asks `/api/uploads` for a presigned PUT (Content-Length is signed), PUTs straight to R2 under `u/<userId>/<uuid>.glb`, then `/complete` checks the stored size and the 12-byte glTF 2 header with a ranged GET before the row turns `ready`; a bad file is deleted. The presigned PUT is create-only (`If-None-Match: *` is signed), so a verified object cannot be overwritten with the still-valid URL. The R2 bucket needs a CORS rule allowing `PUT` with the `If-None-Match` header from the site origin, and a lifecycle rule (or a sweep, not built yet) for objects whose upload never completed.

Credits: the Free grant (50) is paid once per normalised email ever (`signup_grants` survives account deletion; +aliases and Gmail dots fold together) and only after the email is confirmed. Scene generation and prompt edits are still planned in the browser, so their 2/1-credit debit is honour-system until the director moves server-side; renders are the real gate (`create_render_job`, Lane D2).

## Billing (Paddle)

Paddle Billing is the merchant of record. Credits and plans change **only** through the verified webhook; the browser never sends a price or an amount.

- **Catalog** (`lib/billing/catalog.ts`): the browser names a checkout item (`plan:creator`, `plan:pro`, `pack:100`, `pack:500`, `pack:2000`, see `CHECKOUT_ITEMS` in `lib/pricing.ts`). The server maps it to a Paddle price id from env (`PADDLE_PRICE_*`); the webhook maps the paid price id back. Unknown prices grant nothing.
- **Checkout**: `POST /api/billing/checkout {item}` returns the price id, the customer email and custom data `{user_id, user_sig}` (HMAC of the user id, keyed from `PADDLE_WEBHOOK_SECRET`, so nobody can credit, or charge back against, another account). `lib/billing/client.ts` loads Paddle.js v2 from `cdn.paddle.com` and opens the overlay. A plan purchase while a plan subscription is live changes that subscription instead (prorated, via the API). Without `NEXT_PUBLIC_PADDLE_CLIENT_TOKEN` checkout reports "isn't open yet". The Local backend keeps its instant fake grants.
- **Webhook**: `POST /api/billing/webhook` verifies `Paddle-Signature` (`ts=…;h1=…`, HMAC-SHA256 of `ts:rawBody`, Web Crypto, ±5 min), maps the event to one action (`lib/billing/events.ts`) and calls `billing_apply_event()` once. That SQL function records the event id and applies the action in one transaction, so replays are no-ops and failures return 500 for Paddle to retry. Handled: `transaction.completed` (pack → `paddle:txn:<id>`; subscription first payment / renewal / upgrade → `paddle:sub:<sub>:<period_end>:<plan>`, one grant per billing period, an upgrade tops up the difference), `subscription.*` (status, plan, period; out-of-order events ignored by `updated_at`), `adjustment.created/updated` when `approved` (refund / chargeback → negative `billing_reversal` row, proportional to the amount; a reversed chargeback gives it back). The balance may go negative; `create_render_job` and `spend_credits` then refuse everything, free previews included.
- **Plans**: `user_plan(user_id)` is the live entitlement: an active/trialing subscription, or a canceled / past_due / paused one until the end of its last *paid* period, else Free. `profiles.plan` is a display copy kept in sync on every billing event and by `sync_expired_plans()` (schedule it with pg_cron).
- **Plan limits (for the render lane)**: `plan_limits(plan)` and `user_plan_limits(user_id)` in SQL, `PLAN_LIMITS` / `planLimits()` in `lib/pricing.ts` (a test pins them equal): `max_resolution` (free 720p, creator 1080p, pro 4k), `watermark` (free only), `retention_days` (7 / 30 / 90), `priority` (0 / 1 / 2, higher first). Call `user_plan_limits` with the service role when creating a job; it is not wired into render code yet.
- **Portal**: `POST /api/billing/portal` creates a Paddle customer portal session for the caller's Paddle customer and returns its URL ("Manage billing" on the profile for paid plans, and on the Free card for paying users). Account deletion cancels live subscriptions first.
- Tables: `billing_customers`, `billing_subscriptions`, `billing_transactions`, `billing_adjustments`, `billing_events` (migration `*_billing.sql`, pgTAP `supabase/tests/billing.test.sql`). Users can read their own subscription and transactions; everything else is service role only.

## Before wiring the renderer

Known shortcuts in the prototype that real latency will expose; fix these first.

- Render job state lives in `RenderPanel` component state: the `services.render.subscribe` subscription dies when the drawer closes. Move jobs into a store.
- In-flight store actions are not cancelled by `open()` / `reset()`: a slow `submitPrompt` can land on the next project. Guard each resolution with a project-id check.
- `useLabourStore` and `useIngestStore` are module singletons and are not reset on project change.
- The credit-balance refresh is triggered from `Composer` (`onDone`); move it into the studio store so every credit-spending action refreshes.
- Models are parsed twice on ingest: `useModelIngest` (for stats) and then `useStudioModel` (for the viewer). Parse once and hand the root over.
- Scene-generation / prompt-edit credits are debited after the version is saved (`lib/stores/studio.ts`). The server refuses an overdraft, but a failed debit keeps the version; debit first once the director moves server-side.
- The landing hero calls `lib/scene` directly on purpose (a static demo, not the studio); keep it local rather than routing it through the services seam.

## Layout

- `app/` — routes (`/` landing, `/projects` dashboard, `/projects/[id]` studio, `/pricing`).
- `components/viewer/` — the three.js viewer, environments and camera paths.
- `components/studio/` — composer, drawer, analysis and version history.
- `e2e/` — Playwright specs (`studio.spec.ts` full flow, `pages.spec.ts` landing and pricing).
- `lib/scene/` — model analysis and the prompt → scene-plan director.
- `docs/superpowers/` (repo root) — spec and plan this prototype follows.
