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

First e2e run: `npx playwright install chromium`. Everything the studio spec loads is served locally: `/samples/toycar.glb` and the HDR environments under `public/hdri/` (`next/font` fetches Inter at build time). Reports land in `playwright-report/`, traces for failures in `test-results/` (both git-ignored).

## What is and is not here

- Without backend env, everything runs in the browser: projects, versions and credits persist in IndexedDB. With it, see "Backend" below.
- Renders go to RunPod Serverless (the `Rendering-worker` image) only in Supabase mode with `RUNPOD_API_KEY` + `RUNPOD_ENDPOINT_ID` set; Local mode (and a server without those two) answers `not_connected` and the Render tab shows its recovery state. See "Renders" below.
- Services (storage, credits, planning) are swapped at one seam: `lib/services/index.ts`. Replace the local implementations there to talk to a real backend.

## Backend (Supabase + R2)

The service seam (`lib/services/index.ts`) picks the implementation at build time:

- **No `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`** → the in-browser `Local*` fakes (guest mode, demo providers, local ledger). `npm run dev`, vitest and Playwright use this; nothing needs a network.
- **Both set** → `Supabase*` services: real accounts (email + password with verification, Google, password reset, server-side account deletion), projects/versions in Postgres under RLS, the server credit ledger, and model files in R2. Guest mode and the demo providers are gone on this path.

Layout (Supabase CLI, run from `apps/web`): `supabase/config.toml` (local stack only), `supabase/migrations/*.sql` (schema, RLS, `create_render_job`, `refund_render_job`, `save_scene_version`, `spend_credits` (legacy, no caller), new-user trigger granting `free_plan_credits()` = `FREE_PLAN_CREDITS` = 50), `supabase/tests/*.sql` (pgTAP: `supabase start && supabase test db`, local only).

Env: `.env.example` (for `next dev` / build) and `.dev.vars.example` (for `wrangler dev`). `NEXT_PUBLIC_*` are inlined at build time, so they must be set when `npm run cf:build` runs; `SUPABASE_SERVICE_ROLE_KEY` and `R2_*` are read at request time (`wrangler secret put`).

Server pieces: `proxy.ts` (session refresh; redirects signed-out visitors away from `/projects`, `/profile`, `/settings`, `/dev`), `app/api/uploads` (+ `/:id/complete`, `/:id/download`), `app/api/projects/:id` (DELETE), `app/api/projects/:id/versions` (POST), `app/api/account/delete`, `app/auth/callback` and `app/auth/confirm`. The service-role client is created only inside those routes, after `requireUser()`.

Uploads: `.glb` only, ≤ 200 MB. The browser asks `/api/uploads` for a presigned PUT (Content-Length is signed), PUTs straight to R2 under `u/<userId>/<uuid>.glb`, then `/complete` checks the stored size and the 12-byte glTF 2 header with a ranged GET before the row turns `ready`; a bad file is deleted. The presigned PUT is create-only (`If-None-Match: *` is signed), so a verified object cannot be overwritten with the still-valid URL. The R2 bucket needs a CORS rule allowing `PUT` with the `If-None-Match` header from the site origin, and a lifecycle rule (or a sweep, not built yet) for objects whose upload never completed.

Credits: the Free grant (50) is paid once per normalised email ever (`signup_grants` survives account deletion; +aliases and Gmail dots fold together) and only after the email is confirmed. Saving a scene version is the charge point, on the server: `POST /api/projects/:id/versions {prompt, parentId, plan, action, idempotencyKey}` validates the plan with `ScenePlanSchema` and calls `save_scene_version()` once, which, under the per-user credit lock, prices the action with `scene_action_cost()` (generate 2, edit 1, adjust 0; mirrors `CREDIT_COSTS`, pinned by `lib/pricing.test.ts`), debits the ledger (`version:<id>` ref, `scene_generation` / `prompt_edit`) and inserts the version in one transaction. The browser declares an action, never an amount: a project's first version is always a generation, an edit or adjust needs a parent in the same project, and a free `adjust` is refused (400 `not_an_adjustment`) unless it moves only the slider/output fields (`isFreeAdjustment`, `lib/scene/versionAction.ts`). A short or negative balance answers 402 `insufficient_credits` (the studio shows it with a link to /pricing); more than 120 versions per user per hour, 429. A retried save with the same idempotency key returns the saved version, charged once. Users have no INSERT/UPDATE/DELETE on `scene_versions` (`20260929100000_scene_version_credits.sql`), so the route is the only write path; `/api/credits/spend` is gone. Local mode applies the same prices and first-version rule to the in-browser ledger (`LocalProjectRepository.appendVersion`). The director itself still runs in the browser, so the server can check an edit's shape but not that the text really asked for it; renders are gated by `create_render_job` (Lane D2).

## Billing (Paddle)

Paddle Billing is the merchant of record. Credits and plans change **only** through the verified webhook; the browser never sends a price or an amount.

- **Catalog** (`lib/billing/catalog.ts`): the browser names a checkout item (`plan:creator`, `plan:pro`, `pack:100`, `pack:500`, `pack:2000`, see `CHECKOUT_ITEMS` in `lib/pricing.ts`). The server maps it to a Paddle price id from env (`PADDLE_PRICE_*`); the webhook maps the paid price id back. Unknown prices grant nothing.
- **Checkout**: `POST /api/billing/checkout {item}` returns the price id, the customer email and custom data `{user_id, user_sig}` (HMAC of the user id keyed by its own `CHECKOUT_SIGNING_SECRET`, so nobody can credit, or charge back against, another account, and rotating the Paddle webhook secret never strands a paid checkout; see "Checkout signing key" below). `lib/billing/client.ts` loads Paddle.js v2 from `cdn.paddle.com` and opens the overlay. With `PADDLE_API_KEY` set, the route finds or creates the Paddle customer for the account's own verified email and links it server-side (webhooks never link customers, and never resolve an owner from a customer id: Paddle.js runs in the browser, so anyone can check out under someone else's email). A plan purchase while a plan subscription is live changes that subscription instead: an upgrade is charged pro rata, a downgrade is `do_not_bill` (a prorated downgrade would refund money while the higher plan's credits stay granted). Without `NEXT_PUBLIC_PADDLE_CLIENT_TOKEN` checkout reports "isn't open yet". The Local backend keeps its instant fake grants.
- **Webhook**: `POST /api/billing/webhook` verifies `Paddle-Signature` (`ts=…;h1=…`, HMAC-SHA256 of `ts:rawBody`, Web Crypto, ±5 min), maps the event to one action (`lib/billing/events.ts`) and calls `billing_apply_event()` once. That SQL function records the event id and applies the action in one transaction, so replays are no-ops and failures return 500 for Paddle to retry. Handled: `transaction.completed` (pack → `paddle:txn:<id>`; subscription first payment / renewal / upgrade → `paddle:sub:<sub>:<period_end>:<plan>`, one grant per billing period; an upgrade tops up the difference scaled by the share of the period left at the transaction's `billed_at`, never at processing time, so a late or retried delivery grants what Paddle charged), `subscription.*` (status, plan, period; out-of-order events ignored by `updated_at`), `adjustment.created/updated` when `approved` (refund / credit / chargeback → negative `billing_reversal` row, proportional to the amount, and a full reversal of a plan payment also removes the plan for that period; a reversed chargeback gives both back). A grant with no signed owner raises: the webhook answers 500 and Paddle retries, so nothing paid is silently dropped (watch `/admin/billing` for repeats). A refund or chargeback with nothing to take back (its payment granted nothing, e.g. a $0 transaction, or its account was deleted) is held in `billing_unapplied_adjustments` and answered 200 so Paddle stops retrying; it is listed on `/admin/billing`, and if its payment is applied later (Paddle does not order deliveries) the held refund is applied at that moment.
- **Nothing unpaid grants** (migration `20260929210000_billing_hardening.sql`): a transaction whose total after discounts is 0 (a 100% discount code, a trial's first period, a $0 renewal) grants no credits and no plan. Paid from the customer's Paddle credit balance still counts as paid. The one exception is a price listed in `PADDLE_PROMO_PRICE_IDS` (comma-separated, empty by default): a $0 transaction whose every catalog price is listed grants as if paid. To run a giveaway, list that price and restrict the Paddle discount code to it. The balance may go negative; `create_render_job` and `save_scene_version` then refuse everything, free previews and free adjustments included.
- **Plans**: `user_plan(user_id)` is the live entitlement: a subscription that has had at least one *paid* period and is active/trialing, or a canceled / past_due / paused one until the end of its last paid period, else Free. A trialing or 100%-discounted subscription is Free (features and credits) until its first paid transaction. `profiles.plan` is a display copy kept in sync on every billing event and by `sync_expired_plans()`, which the 5-minute cron sweep calls (no pg_cron needed).
- **Plan limits**: one table, only claims the system backs. `PLAN_LIMITS` in `lib/pricing.ts` (the plan cards' render lines are derived from it by `limitFeatures()`) and `plan_limits(plan)` / `user_plan_limits(user_id)` in SQL (migration `20260928150000_plan_limits_v2.sql`; `lib/billing/billing.test.ts` pins them equal). Free: 540p previews only, watermark, 1 render at a time, 7-day retention. Creator: previews + 1080p finals, no watermark, 1 at a time, 30 days. Pro: as Creator, 3 at once, 90 days. There is no 4K (the worker renders 540p or 1080p) and no GPU priority (RunPod has none per job); `plan_rank` only orders upgrades vs downgrades. `create_render_job` enforces all of it (see Renders).
- **Portal**: `POST /api/billing/portal` creates a Paddle customer portal session for the caller's Paddle customer and returns its URL ("Manage billing" on the profile for paid plans, and on the Free card for paying users). Account deletion cancels live subscriptions first, including any Paddle lists for the linked customer that no webhook has recorded yet.
- Tables: `billing_customers`, `billing_subscriptions`, `billing_transactions`, `billing_adjustments`, `billing_events`, `billing_unapplied_adjustments` (migrations `*_billing.sql`, `*_billing_hardening.sql`; pgTAP `supabase/tests/billing.test.sql`, `billing_hardening.test.sql`). Users can read their own subscription and transactions; everything else is service role only.
- **Append-only records**: `credit_ledger`, `admin_audit_log`, `billing_events`, `billing_transactions` and `billing_adjustments` cannot be deleted or truncated, not even by the service role (privileges revoked, and triggers stop the table owner too); the ledger, audit log and adjustments cannot be edited either. Deleting an account keeps its ledger and payment rows with `user_id` set to NULL: amounts, reasons, timestamps and Paddle ids, no email or name. They are bookkeeping records kept under the legal duty to keep accounting records (GDPR art. 17(3)(b)), detached from the erased person; Paddle, as merchant of record, keeps its own copy.
- **Checkout signing key**: `CHECKOUT_SIGNING_SECRET` (a random 32-byte hex string, `wrangler secret put`) signs `custom_data.user_sig`; unset, the webhook secret signs as before (legacy; set the new key before launch). To rotate it, or to move off the legacy fallback: set `CHECKOUT_SIGNING_SECRET=<new>` and `CHECKOUT_SIGNING_SECRET_PREVIOUS=<the key it replaces>` (for the legacy move, the current `PADDLE_WEBHOOK_SECRET`) in the same deploy. The previous key only verifies, so checkouts opened before the switch still credit when Paddle delivers or retries them (up to about 3 days); remove `CHECKOUT_SIGNING_SECRET_PREVIOUS` after 7 days. Renewals do not depend on it (they resolve the owner from the stored subscription). Rotating `PADDLE_WEBHOOK_SECRET` itself no longer affects checkouts.

## Renders (Lane D2)

Contract: `Rendering-worker/worker/README.md` section 1 (`worker/contract.py`). Site side:

- `lib/render/`: the request params (zod, strict, mirrors `parse_params`: `RenderParamsSchema` is what the browser may send, `WorkerParamsSchema` adds the server-only `watermark`), the graded worlds (hand-copied from `py -m engine.site_job worlds`), per-tier cost (`lib/pricing`), plan limits for display (`planLimits.ts`; the server reads `user_plan_limits`), and the pure RunPod status -> job mapping.
- **Plan enforcement** (`20260928150000_plan_limits_v2.sql`): `create_render_job` reads `user_plan_limits` under the per-user credit lock, after the idempotent replay check: a tier the plan lacks raises `plan_required` (403), the concurrent-job limit `too_many_active` (429). It stamps the job with `watermark` and `retention_days` from the plan at creation, and debits as `render_preview` or `render_final` (same `render:<job>` ref, so idempotency is unchanged). A request whose params carry `watermark` is refused (the browser can never set it). `RenderPipeline.create` pre-checks the same limits for a friendly early answer.
- **Watermark**: the worker gets `params.watermark: true` only when the job row says so (`workerParams`). The worker reports `watermarked` (false if its font is missing); it is stored on the job, and a watermarked job that comes back unmarked still succeeds but gets a warning on the row and a log line.
- **Retention** (`lib/server/retention.ts`, run by the sweep): outputs expire `retention_days` after the job finished (`expired_render_outputs` -> delete `video.mp4` + `poster.jpg` -> `mark_render_outputs_expired`; the row stays, the UI shows "Expired", download answers 410). Uploaded models expire when the owner's current plan retention has passed since last use (uploaded or last rendered from), never while a render of them is live; `expire_uploads` claims them first (status `rejected`, reason `expired`, so no new render starts), then the R2 delete and `mark_uploads_purged` (a failed delete is retried next run). Pending uploads abandoned for a day are claimed too. A lapsed paid plan keeps its model retention for 30 days after its paid period (dunning grace). Batches of 100, at most 2 per kind per run.
- `supabase/migrations/20260928140000_render_pipeline.sql`: progress/output/timing columns on `render_jobs`, `render_job_private` (webhook token hash, operator error detail, log tail, pin; no user access) and `finish_render_job()` (the one terminal transition + refund, idempotent per RunPod attempt). pgTAP: `supabase/tests/render_pipeline.test.sql`.
- `lib/server/renderPipeline.ts`: the state machine (create/debit -> presign R2 -> `POST /run` -> progress -> finish; one auto-retry of a retryable failure on the same debit; refunds on every failure, RunPod `CANCELLED`/`TIMED_OUT`, lost jobs and user cancels before the GPU starts).
- Routes: `POST/GET /api/renders`, `GET /api/renders/:id` (polls RunPod when the row is >10 s old), `POST /api/renders/:id/cancel`, `GET /api/renders/:id/download?file=video|poster`, `POST /api/runpod/webhook?job=&t=` (per-job token, constant-time, then re-read `/status` with the API key), `POST /api/renders/sweep` (Bearer `CRON_SECRET`: render re-poll, `sync_expired_plans()`, retention; each chore reported separately, 500 if any failed).
- Outputs: `r/<userId>/<jobId>/video.mp4|poster.jpg` in the same bucket. Sample models render from `samples/<name>.glb` in R2: upload `public/samples/*.glb` there (currently `toycar.glb`, `product.glb`, `watch.glb`, all CC0, see `public/samples/LICENSES.md`) and delete the retired `samples/car.glb`.
- Cron: `custom-worker.mjs` wraps the OpenNext worker and adds `scheduled` (every 5 min, `wrangler.jsonc` `triggers`), which calls the sweep route.
- Mail: "render ready" through Resend when `RESEND_API_KEY` is set (`lib/server/notify.ts`), else a no-op. Same layout as the auth emails (`lib/email/layout.ts`), HTML + plain-text parts, the poster (a 7-day presigned R2 link) and a "View render" link. It respects `profiles.email_render_ready` (Settings -> Notifications, default on); an opted-out job is still marked notified, so it is never retried.
- Client: `HttpRenderService` (polls `/api/renders/:id` with backoff) + `lib/stores/render.ts` (jobs per project, outlive the drawer; resumed on reload).

## Share links

Owners can opt a finished render into a public page at `/r/<slug>` (the growth loop: every shared video carries a "Try Valora3D free" link to `/signup`).

- **Studio**: "Share" on a finished render (`components/studio/RenderResult.tsx` -> `SharePanel.tsx`) opens a small panel: nothing is public until "Create link"; "Show my prompt on the page" is off by default; then "Copy link", the view count and "Stop sharing". `RenderService.getShare/share/unshare` (`lib/services/supabase/render.ts`); Local mode never has a finished render, so it never shows.
- **API**: `GET/POST/DELETE /api/renders/:id/share` (`lib/server/shares.ts`). Owner only: the job must be visible through the caller's RLS client, and the SQL functions check the owner again. POST `{show_prompt}` creates the link or updates the prompt setting on the live one; a second POST never mints a second link. Slugs are 18 random bytes from Web Crypto as base64url (24 characters, 144 bits; `lib/share/slug.ts`). Rate limit: 20 new links per user per rolling hour, enforced in SQL (429 `rate_limited`).
- **Schema** (`supabase/migrations/20260929130000_render_shares.sql`, pgTAP `supabase/tests/render_shares.test.sql`): `render_shares` (slug unique, job_id, user_id, show_prompt, created_at, revoked_at, view_count), RLS on (owners read their own; no user writes), one live share per render, revoking is final for that slug (sharing again mints a new one). Service-role-only functions: `create_render_share`, `revoke_render_share`, `public_render_share` (the only public read: render details only while the share is live and the outputs still exist; the prompt only when ticked), `bump_render_share_view`.
- **Public page**: `app/(public)/r/[slug]/page.tsx` + `components/share/SharedRender.tsx`: the video, the prompt if shown, the CTA and a "Report this video" mailto to support@valora3d.com with the slug. Metadata (`lib/share/public.ts`): `og:type video.other`, `og:video` (+ `secure_url`, type, width, height from the worker's report or the tier/aspect), `og:image` = poster, `twitter:card summary_large_image` (X's player card needs an embeddable iframe, which `frame-ancestors 'none'` forbids). Always `noindex`; `/r/` is disallowed in robots.txt and not in the sitemap. The view count is bumped after the response (`after()`), best effort.
- **Media**: `/r/:slug/video` and `/r/:slug/poster` answer a 302 to a 15-minute presigned R2 GET (inline, right content type); the redirect is cached privately for 2 minutes. The browser then fetches from R2 directly, so Range requests (seeking) work and the Worker streams nothing. The CSP already allows R2 in `media-src` and `img-src`.
- **Revoked / expired**: a page cannot send 410, so `proxy.ts` looks the slug up (`lib/server/shareLookup.ts`, no cookies) and answers revoked or expired links with a self-contained friendly 410 page (`goneHtml`); the media routes answer 410 too. Expired means swept by retention or past `finished_at + retention_days` (the sweep may lag). Unknown slugs (and renders deleted with their project) are 404.
- **Review without a backend**: `/dev/share-page` (`?layout=portrait`, `?prompt=0`) renders the public page and its metadata from a fixture; `/dev/share-page/gone?reason=revoked|expired` is the 410 page; `/dev/render-states` has the Share panel on an in-memory service. `e2e/share.spec.ts` covers them.

## Account: usage & billing history, auth emails

- **Profile -> Usage & billing** (`/profile?tab=billing`, `components/account/UsageBilling.tsx`): current plan with its renewal or end date (from `billing_subscriptions`), balance, "Get credits" and "Manage billing / invoices" (the Paddle portal route; Paddle emails receipts and hosts invoices). Below, the credit history (20 a page: date, plain-words reason from `ledgerLabel` in `lib/account/history.ts`, amount, running balance) and every render across projects (poster, status, date, kept-until / expired, download).
- Reads are RLS-only, with the user's own session: the `credit_history` view (migration `20260929120000_account.sql`, `security_invoker`, running balance as a window sum over the caller's own rows, no payment refs exposed) and `billing_subscriptions`; renders come from `GET /api/account/renders?page=` (user client + short-lived presigned poster links). Local mode reads the in-browser ledger and shows no renders. pgTAP: `supabase/tests/account.test.sql`.
- **Low balance**: under the Render button, one muted line with a link to `/pricing` when the balance is below a Final render's cost.
- **Auth emails** (`supabase/templates/*.html`): confirm signup, magic link, reset password, email change, invite, reauthentication code, plus the password-changed and email-changed security notices. Generated from `lib/email/authTemplates.ts` (edit there, then `WRITE_EMAIL_TEMPLATES=1 npx vitest run lib/email`; the test fails if the files drift, a variable goes missing or a link type is one `/auth/confirm` would refuse). Links use the token-hash flow `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=…`, so they work on another device. Opening one never signs in by itself (login CSRF: anyone can mail someone a link to *their own* account): `GET /auth/confirm` forwards to the `/auth/continue` page, whose button POSTs the token back (same-origin only). A browser that asked for the email here (sign-up, password reset) goes straight on after that click; any other browser first sees a warning, and after signing in "Is this your account? <email>" with a sign-out. Mail scanners that prefetch links no longer burn them. `lib/auth/emailLink.ts`. `supabase/config.toml` wires them for the local stack only.
- **Owner, once per hosted Supabase project** (config.toml is not pushed):
  1. Supabase dashboard -> Authentication -> URL Configuration: Site URL `https://valora3d.com` (the links are built from it).
  2. Authentication -> Email Templates: for each of Confirm signup, Invite user, Magic link, Change email address, Reset password, Reauthentication, paste the subject from `supabase/config.toml` and the whole matching file from `apps/web/supabase/templates/` (`confirmation.html`, `invite.html`, `magic_link.html`, `email_change.html`, `recovery.html`, `reauthentication.html`) into the message body, then Save.
  3. Same page, Security notifications: turn on "Password changed" and "Email address changed" and paste `password_changed_notification.html` / `email_changed_notification.html`.
  4. Use a custom SMTP sender (Authentication -> Emails -> SMTP settings) before launch; the built-in sender is rate-limited and unbranded.
  5. Check: sign up, reset a password and change an email on the live site; each mail should show the Valora3D layout, its button should open a "Continue" page, and Continue should land signed in.
  6. Optional logo: each template has a commented `<img>` placeholder; host a PNG (for example `https://valora3d.com/email/logo.png`) and swap it in `lib/email/layout.ts`, then regenerate.

## Deploy: private beta behind Cloudflare Access

`wrangler.jsonc` notes that Cloudflare Access (Zero Trust) sits in front of both hostnames during the private preview. Paddle and RunPod cannot log in to Access, so without exceptions **every Paddle payment is refused at the edge and never credited** (Paddle gives up after its retries), and every render finishes only through the 5-minute sweep. The cron sweep itself is fine: `custom-worker.mjs` calls the app in-process (`handler.fetch`), never through the public hostname, so it needs no exception.

**Owner, before the first real (or sandbox) payment:** Cloudflare dashboard -> Zero Trust -> Access -> Applications -> the Valora3D application(s) -> Policies -> Add a policy, Action **Bypass**, Include **Everyone**, and scope it to exactly these paths on each hostname (add each as its own path-scoped application, or as a Bypass policy on an application whose domain is the path):

1. `valora3d.com/api/billing/webhook` (and the same path on any other hostname Paddle is pointed at). Authentication is the Paddle-Signature HMAC.
2. `valora3d.com/api/runpod/webhook`. Authentication is the per-job 32-byte token in the URL.

Nothing else: every other path stays behind Access. Check: Paddle -> Developer tools -> Notifications -> the destination -> send a test event; it must show 200 (or 401 for the test's own secret), never a 302/403 from Access.

## Launch hygiene (Lane E)

- **Turnstile (bot protection on sign-up, log-in and password reset):** Supabase Auth checks the
  challenge itself (native CAPTCHA protection), so calling Supabase's public Auth API directly with
  the anon key cannot skip it. The app only renders the widget and passes its token as
  `options.captchaToken` to `signUp` / `signInWithPassword` / `resetPasswordForEmail`. There is no
  Valora3D siteverify call: tokens are single-use, so verifying one ourselves would make Supabase
  reject it. The forms fetch a fresh challenge after every attempt, on expiry and on error.
  - Set `NEXT_PUBLIC_TURNSTILE_SITE_KEY` **at build time**. Blank = no widget, no token (Local mode
    and CAPTCHA-free dev projects keep working).
  - **Owner, once per Supabase project** (do this in the same release that sets the site key; with
    CAPTCHA on and no site key, every sign-up/log-in/reset fails; with the site key and CAPTCHA off,
    the widget shows but bots can still call Supabase directly):
    1. Cloudflare dashboard -> Turnstile -> Add widget for `valora3d.com` (Managed mode). Copy the
       site key and the secret key.
    2. Supabase dashboard -> Authentication -> Attack Protection -> enable **CAPTCHA protection**,
       provider **Turnstile by Cloudflare**, paste the **secret** key, Save.
    3. Build with `NEXT_PUBLIC_TURNSTILE_SITE_KEY=<site key>` and deploy.
    4. Check: sign up, log in and request a reset on the live site; each should succeed after the
       challenge. The secret key lives only in Supabase, never in this app's env or Worker secrets.
- **Logs:** Workers observability is enabled. `lib/server/log.ts` emits fixed event names,
  route templates, generated request IDs and verified user UUIDs where known. It never accepts
  raw exceptions, headers, emails, tokens or request URLs. The global error boundary sends only
  `{ "event": "global_error" }` to `/api/client-errors` (1 KiB maximum, same-origin JSON only).
  The `HYGIENE_RATE_LIMITER` binding permits 10 requests/minute per route and Cloudflare client IP
  in each Cloudflare location; IPs are used only for limiting, never logged by this logger.
  Namespace `1003` must be reserved for this limiter in the Cloudflare account. The standalone
  Next server uses a bounded, process-local bucket of 10 requests/minute instead.
- **Analytics:** set `NEXT_PUBLIC_CF_ANALYTICS_TOKEN` at build time to load the optional Cloudflare
  Web Analytics beacon. Leave it blank to omit the script. The privacy draft discloses cookieless
  analytics. Avoid putting personal data in URLs. Disable Cloudflare's automatic beacon injection
  if using this application-managed beacon to avoid double counting.
- **Checks:** `e2e/accessibility.spec.ts` runs axe on public pages, the 404 and Local studio states.
  The existing landing tests check keyboard pause/resume and reduced-motion playback. CI uses
  Node 24 and Local mode and runs lint, typecheck, Vitest, Chromium e2e and the OpenNext build.
  If Windows hangs during Playwright's server teardown, start `npm run dev` separately and set
  `E2E_REUSE_SERVER=1` for the test command; CI never reuses a server.
- **Contact files:** `/.well-known/security.txt` expires on 2027-09-28; renew before that date.
  `/humans.txt` lists the project and asset credits. The owner must provision/monitor the security
  mailbox and verify live Turnstile (Supabase CAPTCHA), Supabase email flows and the analytics dashboard before launch.

## Admin console (`/admin`)

The owner's console, so day-to-day operations never need the Supabase dashboard. Migration
`20260929110000_admin_console.sql`, pgTAP `supabase/tests/admin_console.test.sql`.

- **Who**: rows in `public.admins`. Make the owner an admin once, after they have signed up (Supabase dashboard -> SQL editor):
  ```sql
  insert into public.admins (user_id, note)
  select id, 'owner' from auth.users where lower(email) = lower('owner@example.com')
  on conflict (user_id) do nothing;
  ```
  Remove: `delete from public.admins where user_id = '<uuid>';`
- **Three checks**: `proxy.ts` (the user's own session reads their own `admins` row under RLS; a non-admin, signed in or
  not, gets the ordinary 404 page for `/admin/*` and a 403 for `/api/admin/*`), the `/admin` layout (server-side, again),
  and every `/api/admin/*` route (`requireAdmin()` in `lib/server/admin.ts`, service role). The `admin_*` SQL functions
  re-check `is_admin()` themselves. `/admin` is `noindex` (meta + `X-Robots-Tag`), `no-store`, and in neither the
  sitemap nor robots.txt (listing it there would advertise it).
- **Screens**: Overview (signups, paying users per plan, credits granted/spent, renders by status, failure rate, average
  render time, GPU seconds, gross revenue per currency; 24 h / 7 d / 30 d), Renders (filter by status / user; job detail
  with error code, operator detail, log tail, pin, timings, ledger), Users (search by email fragment or id; plan, balance,
  ledger, jobs, uploads, billing), Billing (failed webhook deliveries, unmatched/stale events, transactions,
  refunds/chargebacks), Audit.
- **Actions** (each writes one `admin_audit_log` row: admin id, action, target, reason, result; the log is append-only):
  - *Adjust credits*: `admin_adjust_credits` writes the ledger row (`admin_adjustment`, ref `admin:credits:<request id>`)
    and the audit row in one transaction. Reason required. A deduction may take the balance below zero.
  - *Refund render*: `admin_refund_render_job` calls the existing `refund_render_job` (a job is refunded at most once,
    whoever asks) and records `refunded_credits`.
  - *Retry render*: a failed job the worker marked retryable is resubmitted through the normal pipeline as a new job
    (same model and settings; the user pays the normal cost, the failed attempt having been refunded; plan limits apply).
    Its idempotency key is `admin-retry-<job id>`, so a failed job is retried at most once.
  - Every action carries a request id minted when its form opens and resent on a retried click, so the database applies
    it once (a reused id with different details is refused, 409).
- **Webhook errors**: a failed `billing_apply_event` rolls back its `billing_events` row, so the webhook now also writes
  `billing_webhook_errors` (stage config / parse / apply, only after the signature verified; best-effort, 90 days).
  Nothing but `/admin` reads it.
- **Local mode**: `/admin` says it needs the live backend and every admin API answers 403. `/dev/admin` (dev only) shows
  the screens with sample data for design review.

## Before wiring the renderer

Known shortcuts in the prototype that real latency will expose; fix these first.

- In-flight store actions are not cancelled by `open()` / `reset()`: a slow `submitPrompt` can land on the next project. Guard each resolution with a project-id check.
- `useLabourStore` and `useIngestStore` are module singletons and are not reset on project change.
- The credit-balance refresh is triggered from `Composer` (`onDone`); move it into the studio store so every credit-spending action refreshes.
- Models are parsed twice on ingest: `useModelIngest` (for stats) and then `useStudioModel` (for the viewer). Parse once and hand the root over.
- The landing hero calls `lib/scene` directly on purpose (a static demo, not the studio); keep it local rather than routing it through the services seam.

## Layout

- `app/` — routes (`/` landing, `/projects` dashboard, `/projects/[id]` studio, `/pricing`).
- `components/viewer/` — the three.js viewer, environments and camera paths.
- `components/studio/` — composer, drawer, analysis and version history.
- `e2e/` — Playwright specs (`studio.spec.ts` full flow, `pages.spec.ts` landing and pricing).
- `lib/scene/` — model analysis and the prompt → scene-plan director.
- `docs/superpowers/` (repo root) — spec and plan this prototype follows.
