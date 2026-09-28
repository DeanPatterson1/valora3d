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
| C: payments | Paddle checkout + webhook to the ledger; customer portal link; plan limits enforced server-side | after A | todo |
| D1: render worker | Dockerfile (Linux Blender 5.0.1 + engine); RunPod handler: fetch GLB from R2, run `site_job`, encode MP4 + poster with ffmpeg, upload to R2, report progress | Opus agent, in the `Rendering-worker` worktree | code done 2026-09-28 on `worker/runpod` (5 commits, 112 pytest). Image never built (no Docker). Contract: `worker/README.md`. Engine asks: `site_job --markers`, ingest rejects exit 5, `--script` so directing runs off the GPU box |
| D2: site render pipeline | `HttpRenderService`; job API (create/status/cancel); RunPod webhook; new inputs (prompt, world, aspect, tier, `.glb` only) matching the `site_job` contract; reuse `provider.ts`/job-store pieces from `claude/local-site-setup-84943c` | after A + D1 | todo |
| E: launch hygiene | Sentry-style error logging, analytics (Cloudflare Web Analytics), axe pass, CI (GitHub Actions: lint/test/typecheck/e2e) | after B | todo |

## Owner-only (accounts / money / legal)
1. Create a Supabase project (free tier) and hand over the URL + anon key + service-role key (via `wrangler secret`, never pasted in chat).
2. Create a Paddle account + business verification; decide prices (credit packs / plans).
3. Create a RunPod account + API key; set a monthly spend cap.
4. Cloudflare: Workers Paid plan (needed for R2 bindings at scale / CPU limits), create an R2 bucket, Turnstile site key.
5. A Resend account + DNS records for valora3d.com.
6. Legal: review the drafted terms/privacy/refund; confirm the GT3 RS / 720S gallery licence covers SaaS marketing.
7. Go-live: lift Cloudflare Access; the marketing hold is still on.
