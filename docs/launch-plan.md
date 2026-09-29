# Valora3D launch plan

Started 2026-09-28. Goal: the site is launch-ready the day the renderer (`engine/site_job.py`,
renderer-engine track) is finished. Audits behind this plan (2026-09-28): the web audit found every
service is a `Local*` fake, with no API, database or storage; the renderer audit covered the
`site_job` contract, the GPU options and the security of uploads.

## Stack (owner decisions 2026-09-28)
| Concern | Choice |
|---|---|
| Accounts, projects, credit ledger, jobs | Supabase (Auth + Postgres + RLS), via `@supabase/ssr` on Workers |
| Uploads + render outputs | Cloudflare R2, with presigned PUT/GET and a key per user prefix |
| Payments | Paddle Billing (merchant of record); credits are granted only by a verified webhook |
| Renders | RunPod Serverless GPU: a Docker image with Blender 5.0.1 plus `engine/`, whose handler calls `site_job` |
| Email | Supabase Auth emails (verification, reset) + Resend for "render ready" and receipts |
| Abuse | Cloudflare Turnstile on sign-up, Workers rate limits on the API |

## Security rules (non-negotiable)
- Uploads are `.glb` only, checked server-side (magic bytes, size, `engine/ingest` limits). The worker imports them inside a container with no network.
- Credits live only on the server: they are debited in the same transaction as the job is created, and refunded on failure. The browser never writes the ledger.
- The Paddle webhook is signature-verified and idempotent on the event id.
- RLS is on for every table; the service role is used only inside API routes and never shipped to the client.
- Secrets live only in `wrangler secret` / `.dev.vars`, never in git.

## Lanes
| Lane | Scope | Owner | Status |
|---|---|---|---|
| A: backend foundation | Supabase schema/migrations/RLS; real Auth, Project, Credit and Upload services; route middleware; env plumbing; per-user data | Opus agent, in the `Valora3D` worktree | code done 2026-09-28 (`f50b035..4d81279`): lint/typecheck/vitest 407/cf:build green, proxy smoke-tested on workerd. Not yet run: pgTAP (needs `supabase start`), anything against a real project (needs owner keys) |
| B: public + trust | public `/pricing`; drafts of terms/privacy/AUP-DMCA/refund; contact; de-prototype copy; remove placeholder reviews; SEO (robots, sitemap, metadata, OG); not-found/global-error; security headers + CSP; `/dev/*` hidden in prod; hero pause; fix stale e2e | Codex draft, then Claude review, in the `Valora3D-trust` worktree | merged 2026-09-28: e2e 21/21 in dev and production (`/dev` returns 404 via `proxy.ts`). Owner still to fill the legal placeholders (operator name/address, governing law, DMCA agent, retention periods) |
| C: payments | Paddle checkout + webhook to the ledger; customer portal link; plan limits enforced server-side | Opus agent, in the `Valora3D-pay` worktree | code done 2026-09-28 on `site/paddle`: signed webhook -> `billing_apply_event` (idempotent on event id + ledger ref), packs, monthly plan grants, upgrades, refunds/chargebacks (balance may go negative, renders blocked), portal, `user_plan_limits()` for D2. lint/typecheck/vitest/cf:build/e2e green; pgTAP run on PGlite only. Not yet run: anything against Paddle sandbox (needs owner account). **Merged + integrated 2026-09-28** into `site/valora3d-preview` (`ac67d6d`, integration pass below) |
| D1: render worker | Dockerfile (Linux Blender 5.0.1 + engine); RunPod handler: fetch GLB from R2, run `site_job`, encode MP4 + poster with ffmpeg, upload to R2, report progress | Opus agent, in the `Rendering-worker` worktree | code done 2026-09-28 on `worker/runpod` (5 commits, 112 pytest). Image never built (no Docker). Contract: `worker/README.md`. Engine asks: `site_job --markers`, ingest rejects exit 5, `--script` so directing runs off the GPU box |
| D2: site render pipeline | `HttpRenderService`; job API (create/status/cancel); RunPod webhook; new inputs (prompt, world, aspect, tier, `.glb` only) matching the `site_job` contract; reuse `provider.ts`/job-store pieces from `claude/local-site-setup-84943c` | after A + D1 | **merged + integrated 2026-09-28** (`098667c`, then the integration pass): plan limits v2 (no 4K / no priority claims; Free 540p previews + watermark + 1 at a time + 7 d, Creator 1080p finals + 30 d, Pro 3 at once + 90 d), enforced in `create_render_job` under the credit lock; `params.watermark` injected server-side from the plan (browser cannot send it), worker's `watermarked` stored; ledger `render_preview` / `render_final`; retention sweep (R2 outputs + models, rows marked, UI "Expired") and `sync_expired_plans()` on the same cron. pgTAP 4 files green on a PGlite harness (not in repo). Not yet run: anything against real Supabase / R2 / RunPod |
| E: launch hygiene | Sentry-style error logging, analytics (Cloudflare Web Analytics), axe pass, CI (GitHub Actions: lint/test/typecheck/e2e) | Codex draft + Opus review, `Valora3D-hygiene` worktree | **merged 2026-09-28**: Turnstile via Supabase NATIVE CAPTCHA (`captchaToken` on sign-up/log-in/reset; no own siteverify), Workers observability + fixed-event logger + `/api/client-errors`, CF Web Analytics (env-gated), axe e2e, `.github/workflows/web.yml` (no remote yet), security.txt. Also: scene settings reduced to Preview 540p / Final 1080p + aspect (`a9aad00`) |

Combined branch gates (2026-09-28, after every merge): lint, typecheck, vitest 571, cf:build, e2e 29+1 dev / 30 production.

## Still code-side (Claude), not blocking account setup
- Engine asks (renderer-engine track): `site_job --markers`, ingest rejections exit 5, `--script` so directing runs off the GPU box (removes the Anthropic key from the worker).
- First real Docker build + RunPod test render; measure cold start, cost per clip; then set credit prices from real cost.
- Run pgTAP on a real `supabase start` once Docker exists.
- Hero upgrade (renderer track): re-render the GT3 RS / 720S clips with the badge/crest meshes hidden, so the hero can be a premium car without readable trademarks (owner chose "de-badged hero" 2026-09-28; the CC0 toy car is the stopgap).
- ~~Replace the studio sample `car.glb` (ModVision M4 — traced, not commercially usable) with CC0 samples~~ Done 2026-09-28: `toycar.glb`, `product.glb` (camera), `watch.glb`, all CC0 (`apps/web/public/samples/LICENSES.md`). Owner: upload them to R2 `samples/` and delete `samples/car.glb` there.

## Owner-only (accounts / money / legal) — walk through in this order
1. **Supabase** (separate Supabase account from ModVision): create a project. ⚠️ The first secret key (`sb_secret_T1KX…`) was pasted in chat 2026-09-28 — revoke it and create a new one before use. → give URL + anon key (build-time) + service-role key (`wrangler secret`). Then apply migrations (`supabase db push`), turn on confirm-email, add Google OAuth, allow `https://valora3d.com/auth/callback`.
2. **Cloudflare**: Workers Paid plan; **Access Bypass for `/api/billing/webhook` and `/api/runpod/webhook`** on every hostname behind Access (payments are never credited without it; exact clicks in `apps/web/README.md`, "Deploy: private beta behind Cloudflare Access"; the cron sweep runs in-process and needs none); R2 bucket `valora3d-uploads` + S3 API token + CORS (PUT with `If-None-Match`) + abandoned-multipart lifecycle; Turnstile widget → site key to the site, secret key into Supabase → Authentication → Attack Protection (both in the SAME release); optional Web Analytics token.
3. **Paddle** (sandbox first): 2 monthly prices (Creator, Pro, no trials), 3 packs (100/500/2000), client token, API key (customer portal, subscriptions, customers), a random `CHECKOUT_SIGNING_SECRET` (`openssl rand -hex 32`, `wrangler secret put`; signs checkout custom data, separate from the webhook secret), leave `PADDLE_PROMO_PRICE_IDS` empty unless running a giveaway, notification destination `https://valora3d.com/api/billing/webhook` for `transaction.completed`, `subscription.*`, `adjustment.*`. Business verification for live. Final prices.
4. **RunPod**: account, API key, monthly spend cap; Docker Desktop (or CI) to build + push the worker image; serverless endpoint (RTX 4090 / L40S, min 0, execution timeout raised).
5. **Anthropic**: a dedicated API key with a low monthly cap for the worker.
6. **Resend**: account + DNS records for valora3d.com; `security@` and `support@` mailboxes.
7. **Legal**: fill the draft placeholders (operator name/address, governing law, DMCA agent, retention), review; confirm the GT3 RS / 720S gallery licence covers SaaS marketing.
8. **Go-live**: lift Cloudflare Access — marketing hold still on.
