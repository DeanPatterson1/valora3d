# Render Core and GPU Queue — real users render videos with the director engine

    date:      2026-09-28
    track:     render-core
    status:    DRAFT for owner review (planning only; no source code changed)
    builds on: docs/superpowers/specs/2026-09-24-director-layer-design.md (the "director spec")
               docs/superpowers/specs/2026-09-19-renderer-engine.md (the "engine spec", §10 conflicts)
               docs/superpowers/plans/2026-09-28-director-phase6-physics-sim.md (§budgets, phase-7 farm facts)
               research/physics/PHASING.md §2 Phase 7 (farm requirements a-c)
    plan:      docs/superpowers/plans/2026-09-28-render-core-p1-private-beta.md (P1 in full, P2/P3 outline)

The director engine turns a model and a prompt into a finished clip, but only on the owner's PC,
from a command line. This spec designs the **render core**: the shared service that lets real users
of two products queue renders, watch their place in line, pay in credits, and get their video.

- **Valora3D** (Next.js on Cloudflare Workers, `apps/web`, branch `site/valora3d-preview`, behind
  Cloudflare Access). Every service in `apps/web/lib/services/local/*` is a browser-local stand-in.
  `LocalRenderService` answers `not_connected` on purpose (engine spec §10.2 tripwire).
- **ModVision Render Studio** (dev-only, `js/render-studio/*` + `tools/render-studio/server.py`).
  It already has Supabase-token auth, per-user job ownership and 1-active / 10-per-day limits, but it
  runs a loopback server on the owner's PC and keeps videos there.

Both front-ends become thin clients of one core. The GPUs **pull** work outbound; nothing listens.

---

## 1. Goals and non-goals

**Goals**

1. A signed-in user submits a job and sees **"You're #3 · ~12 min"**, which stays honest while
   they wait. Their position and ETA are computed from **measured** per-block cost.
2. **Fairness.** Round-robin by user, not FIFO by job. A person with 20 queued jobs cannot bury
   someone else's one job.
3. **Short jobs are not stuck behind long ones.** A 15-minute preview is not stuck behind an
   8-hour final.
4. **Money is exact.** Credits are reserved at enqueue, charged once on success, and refunded
   automatically on failure or cancel. Crashes, retries and resumes never double-charge.
5. **Crash-proof.** A dead worker's work returns to the queue. The job resumes from the last
   finished frame.
6. **The owner PC is worker #1**, with an on/off switch and quiet hours. Rented GPUs join in P2
   and scale with the queue, under a hard spend cap.
7. **Licence-safe.** A ModVision car only reaches a downloadable video when its licence allows
   video export. It carries its credit line.
8. **Observable.** An admin queue view shows who is waiting, what each GPU is doing, spend, and
   cost per clip.

**Non-goals (v1 of the core)**

- The approach-B `bpy` escape hatch (director spec §8).
- Audio (director spec §12 Q3).
- Public launch. That is P3, gated on the owner lifting the marketing hold.
- Real money before P3. P1 credits are granted, never bought.

---

## 2. Hard constraints (restated so every later section can cite them)

| # | Constraint | Source |
|---|---|---|
| H1 | **No local server ever faces the internet.** Workers make outbound HTTPS calls only, and nothing connects inbound. The owner PC opens no port. | owner security rule; ModVision memory "Security pre-launch" |
| H2 | **The LLM emits data, uploads are untrusted.** Blender runs with `--factory-startup --disable-autoexec`, and farm workers hold no credentials beyond job I/O. | director spec §7 |
| H3 | **Same GPU model, Blender build and asset hashes** for every worker on one job's final ranges. Each worker renders whole ranges, never alternating frames. | director spec §4.7 |
| H4 | **The site only delivers owner-graded blocks:** `site_catalog()` and `site_deliverable()` are used on every job. | `engine/director/site.py` |
| H5 | **Monochrome UI** (white accent, no gold), and the **visual-creator pattern**: pictures not terms, one CTA, technical controls hidden under Fine tune. | owner rules |
| H6 | **Cost per clip is measured, not guessed.** GPU-seconds are logged per block combination, and bake-seconds are logged separately. | director spec §4.7; PHASING Phase 7(c) |
| H7 | **Marketing hold.** No public launch until the owner lifts it. Small private tests are OK. | owner 2026-09-25 |

---

## 3. Measured cost envelope (what the queue must survive)

| Workload | Seconds per frame | 10 s clip | Source |
|---|---|---|---|
| Rain film, 1080p, 192 spp | ~35 | 300 f ≈ **2.9 GPU-h** | director spec §4.7 |
| Rain courtyard final, 1080p, 1024 spp | 80–112 | 300 f ≈ **6.7–9.3 GPU-h** | `ModVision/tools/render-studio/jobs.py` `DEFAULT_SECONDS_PER_FRAME` (2026-09-28, RTX 5080) |
| Rain courtyard preview, 540p, 16 spp, frame_step 2 | 6.5–7.5 | 150 f ≈ **17–19 min** | same |
| Product render | 2–4 | 300 f ≈ 10–20 min | director spec §4.7 |
| Volumes / smoke | ×1.5–3 on top (eng) | 4–9 GPU-h | phase-6 plan §budgets |

**The consequence the design must face.** Current `engine/compiler/tiers.py` final is 1024 spp. At
that setting one RTX 5080 finishes about **2–3 world-heavy finals per day**. The two measured rain
numbers above differ by 3× (192 vs 1024 spp). Sample count is therefore the biggest price lever;
director spec §12 Q2 still owns that decision. For P1 the queue assumes the worst row and
compensates:

- Finals default to the **overnight lane** on the owner PC.
- A small weekly finals allowance applies per beta user (§8.4).
- Previews are the everyday product.

Every number in this table is replaced by the cost model (§6.6) as soon as real ranges are logged.

---

## 4. Stack decision

**Recommendation.** **Supabase Postgres** holds all state: queue, ledger, auth for Valora, RLS and
reports. **Cloudflare R2** holds every blob. **One Cloudflare Worker, `render-api`,** is the only
door. Workers and both front-ends talk only to `render-api`. Scheduled work runs as that Worker's
**Cron Triggers**.

```
 Valora (Workers, Access) ─┐                      ┌─ Supabase (render-core project)
 ModVision Render Studio ──┼─ HTTPS ─► render-api ┼─   Postgres: jobs, tasks, workers, ledger,
 Admin view ───────────────┘  (CF Worker, crons)  │   reservations, cost_samples, licences; RLS; Auth
                                   ▲              └─ R2 bucket `render-core`: uploads/, jobs/<id>/…
   owner PC worker ── outbound ────┤                 (presigned, short-lived, per-object URLs)
   rented GPU workers (P2) ────────┘  claim / heartbeat / progress / complete — pull only (H1)
```

### 4.1 Why Postgres for the queue (vs Cloudflare Queues / D1 / Durable Objects)

| Need | Postgres (Supabase) | Cloudflare Queues | D1 | Durable Object scheduler |
|---|---|---|---|---|
| Visible position + ETA ("#3 · ~12 min") | One SQL view over the queue. | **No.** Messages are opaque, with no rank or peek. | Possible | Possible (custom code) |
| Fair share / lanes / priority / aging | One `ORDER BY` over window functions (§6.2). | **No.** FIFO only. | Possible, hand-rolled | Possible, hand-rolled |
| Cancel/edit while queued | Row update | **No.** A message cannot be removed. | Yes | Yes |
| Exactly-once claim across many workers | `FOR UPDATE SKIP LOCKED`, the textbook job-queue primitive | Visibility timeout (at-least-once) | Single writer, no row locks | Single-threaded object (fine) |
| Atomic "reserve credits + enqueue" | One transaction | Separate systems | Yes | Must co-locate the ledger in the DO |
| Ledger, reports, cost-per-clip SQL, admin queries | Native, with joins | — | SQLite (OK) | Custom |
| Auth for Valora users, RLS | Built in (Supabase Auth + RLS) | — | — | — |
| Backups / PITR for a money ledger | Pro plan | — | Time Travel | Custom |
| Team familiarity | ModVision already runs on Supabase (auth, RLS audits, the drafted `renders` SQL) | New | New | New |

A single Durable Object running a scheduler over its own SQLite is the only real rival. It would
work, but it would rebuild auth, RLS, reporting and backups that Supabase already has. **Queues is
the wrong primitive:** it cannot tell a user their position and cannot remove a cancelled job.

### 4.2 Why R2 for blobs (vs Supabase Storage)

- **Size.** Final frames are ~3–6 MB PNG × 300 per clip (~1.5 GB transient). Uploads are up to
  200 MB (`MAX_UPLOAD_BYTES`), and bake caches run to GBs (phase-6 table).
- **Cost.** R2 has zero egress. Rented workers in P2 download inputs from anywhere.
- **Already in use.** Both products are already on Cloudflare. ModVision already serves models from
  R2 (`MV_ASSET_BASE`).
- **Access.** Presigned URLs scope a worker to one object for 15 minutes (H2).
- **The ModVision draft** `docs/security/2026-09-28-render-videos-bucket.sql` (private `renders`
  bucket + table) is **superseded, not run**. ModVision videos live in the core under
  `jobs/<jobId>/`. The draft's lessons carry over:
  - owner-only reads;
  - flat per-user object names so account deletion is complete;
  - per-user caps.

### 4.3 Why one `render-api` Worker (vs Supabase Edge Functions / Next route handlers)

- **Tooling.** Node and Wrangler are already on this machine and in `apps/web`. Deno and the
  Supabase CLI are not installed. Tests run in Vitest and Miniflare.
- **R2 binding.** R2 is a native binding. Presigning uses the S3 API with an R2 token held only in
  this Worker.
- **Secrets.** The Supabase **service role key lives only here.** Browsers get RLS-limited reads.
  Workers get scoped worker tokens.
- **One door.** One gateway serves two tenants, so auth, rate limits and abuse checks are written
  once.
- **Access.** Valora keeps Cloudflare Access on `valora3d.com`. The API lives on
  `render-api.valora3d.com`, whose Access policy is **bypass**, because every route authenticates
  itself and workers cannot do interactive Access login. P2 option: also require an Access
  *service token* on `/v1/worker/*` as a second lock.

### 4.4 Business logic lives in Postgres functions

These functions are the single source of truth for what the queue means. The API and the admin view
both call them, so they can never disagree:

- `enqueue_job`
- `claim_next`
- `heartbeat`
- `report_frames`
- `complete_task`
- `fail_task`
- `cancel_job`
- `edit_job`
- `reap_leases`
- `queue_status`

The **same `runnable_order` view** feeds both `claim_next` and the position/ETA calculation, so the
"#3" a user sees is literally the order the GPUs pull in.

### 4.5 Identity: one core, two tenants

- **`tenant = 'valora'`.** Users sign in with **Supabase Auth in the render-core project**. P1 uses
  email magic links and invite codes. Google sign-in comes later and needs an OAuth client, which is
  owner-only.
- **`tenant = 'modvision'`.** Users keep their ModVision Supabase accounts. `render-api` verifies the
  bearer token by calling the ModVision project's `/auth/v1/user`, cached 60 s by token SHA-256. This
  is the pattern proven in `tools/render-studio/server.py` `SupabaseAuth`, and it needs no JWT-key
  migration.
- **Accounts.** A core `accounts` row is `(tenant, external_user_id)`. Credits, caps, jobs and
  variety memory hang off the account. ModVision's `delete-account` function calls
  `DELETE /v1/accounts/me` so a deleted ModVision user's renders and rows go too.
- **Why a separate Supabase project** rather than ModVision's:
  - Valora users are not ModVision users (privacy, brand).
  - ModVision's F5 200-object quota trigger counts every bucket.
  - A render-core outage or migration cannot touch ModVision's forum, garage or feedback.

---

## 5. Data model (Postgres)

The tables live in the `public` schema of the dedicated render-core project, so PostgREST serves
them with no "exposed schemas" dashboard step. This doc writes them as `core.<name>` for clarity; the
DDL names them `rc_<name>`. All tables have RLS on. Browsers use `authenticated` with policies. Everything else goes through
`render-api` with the service role. Column lists are the contract; the plan writes the DDL.

| Table | Purpose / key columns |
|---|---|
| `tenants` | `id text pk` (`valora`, `modvision`), `allowed_origins text[]`, `auth_kind` (`core_supabase` \| `remote_supabase`), `auth_url` |
| `accounts` | `id uuid`, `tenant`, `external_user_id`, unique(tenant, external_user_id), `plan` (`beta`\|`free`\|`creator`\|`pro`\|`dev`), `weight numeric` (fair-share weight), `role` (`user`\|`admin`), `notify_email bool`, `email`, `status` (`active`\|`suspended`), `tz`, timestamps |
| `invites` | `code_hash`, `grant_credits`, `max_uses`, `used`, `expires_at` (P1 invite-only) |
| `ledger` | Append-only money movements: `account_id`, `amount int` (+grant/+purchase/−capture/+refund/±adjust), `kind`, `job_id`, **`idem_key text unique`**, `note`, `created_at`. There is no UPDATE/DELETE grant, and a trigger rejects both. |
| `reservations` | `job_id pk`, `account_id`, `amount`, `status` (`held`\|`captured`\|`released`\|`partial`), `captured int`, timestamps. **Available = Σ ledger − Σ held reservations.** |
| `prices` | `(tenant, plan, tier, lane)` → credits. Seeded from `apps/web/lib/pricing.ts` `CREDIT_COSTS`. The quote is frozen on the job at enqueue. |
| `jobs` | `id uuid`, `account_id`, `tenant`, `kind` (`preview`\|`final`\|`stills`), `lane` (`short`\|`standard`\|`overnight`), `state` (§6.1), `input` jsonb (prompt, markers, aspect, world, duration, paint, snapshot key + sha256, model key for licences), `quote_credits`, `est_gpu_s`, `enqueued_at`, `started_at`, `finished_at`, `pin` jsonb (gpu_model, blender_build, engine_sha, assets_hash), `script_key` (R2), `result_key`, `poster_key`, `credit_line`, `error_user`, `error_detail`, `idem_key unique` (double-click safe), `parent_job_id` (a final made from a preview), `notify` jsonb |
| `tasks` | `id`, `job_id`, `seq`, `kind` (`ingest`\|`direct`\|`bake`\|`render`\|`encode`), `pool` (`trusted`\|`gpu`\|`cpu`), `state` (`blocked`\|`ready`\|`leased`\|`done`\|`failed`\|`cancelled`), `frame_start`, `frame_end`, `frames_done int[]` (sorted, the resume point), `est_s`, `lease_worker`, `lease_expires_at`, `attempts`, `max_attempts`, `last_error` |
| `workers` | `id`, `name`, `pools text[]`, `provider` (`owner-pc`\|`runpod`\|…), `gpu_model`, `blender_build`, `engine_sha`, `token_hash`, `accepting bool` (the ON/OFF switch), `quiet_hours` jsonb (tz + windows), `hourly_cost_usd`, `trusted bool` (may hold the LLM key and run `direct`), `last_seen`, `last_job_id` (stickiness), `state` (`idle`\|`busy`\|`draining`\|`off`) |
| `cost_samples` | Per finished task: `job_id`, `task_kind`, `tier`, `blocks_sig` (sorted block refs), `world`, `short_side`, `samples`, `frames`, `gpu_model`, `gpu_s`, `bake_s`, `setup_s`, `usd`. Feeds the estimator (§6.6) and the per-clip report (H6). |
| `licences` | `(tenant, model_key)` pk, `allows_video_export bool`, `allows_download bool`, `credit_line text`, `requires_visible_credit bool`, `evidence_ref text` (a path in `ModVision/docs/licensing/`), `reviewed_at`, `reviewed_by` |
| `outbox` | Notifications to send: `account_id`, `channel` (`email`\|`push`), `template`, `payload`, `sent_at`, `attempts` |
| `reports` | Abuse reports on a job or model: `reporter`, `job_id`, `reason`, `state` |
| `events` | Append-only audit: job and worker transitions, admin actions (who, what, when) |
| `settings` | Singleton knobs, each an **(eng)** number in the calibration register: `short_lane_max_s`, `age_promote_s`, `range_target_s`, `lease_s`, `heartbeat_s`, `max_attempts`, `daily_spend_cap_usd`, `wait_target_s`, `queue_paused`, `lane_paused` |

---

## 6. The queue

### 6.1 Job and task lifecycle

```
enqueue ──► QUEUED ──(ingest/direct claimed)──► PREPARING ──(first render range)──► RENDERING
   │           │  cancel/edit                         │                                 │
   │           ▼                                      ▼ (all ranges done)               │
   │      CANCELLED (reservation released)          ENCODING (encode+QC task) ──► UPLOADING ──► COMPLETE
   │                                                                                   (capture once)
   └── any task exhausts max_attempts, or QC fails twice ──► FAILED (reservation released)
```

- `jobs.state` maps 1:1 onto Valora's `RenderJobStatus` (`QUEUED | PREPARING | RENDERING |
  ENCODING | UPLOADING | COMPLETE | FAILED`), plus a new `CANCELLED`.
- **Tasks are created at enqueue** as a small graph:
  - `ingest` (trusted pool) → `direct` (trusted pool; holds the LLM key) → optional `bake` (cpu
    pool, phase-6 sims) → `render` ranges (gpu pool) → `encode` (cpu or gpu).
  - `render` ranges are **split after `direct`**, because only the script knows the frame count
    and blocks.
  - A downstream task is `blocked` until its parents are `done`.
- **Director stage placement.** `ingest` needs Blender; `direct` needs the Anthropic key. Both run
  only on `trusted` workers. In P1 that is the owner PC. In P2 it is a small owned CPU box that
  also pulls. Rented GPUs never hold the key (H2).

### 6.2 Scheduling order: fair share, lanes, priority, aging

One view, `core.runnable_order`, ranks every `ready` task:

```sql
-- sketch; the plan's Task C5 owns the real text and its tests
with q as (
  select t.*, j.account_id, j.lane, j.enqueued_at, a.weight,
         dense_rank() over (partition by j.account_id order by j.enqueued_at, j.id) as user_turn
  from core.tasks t join core.jobs j on j.id = t.job_id join core.accounts a on a.id = j.account_id
  where t.state = 'ready' and j.state not in ('CANCELLED','FAILED','COMPLETE')
)
select *,
  case when lane = 'short' or now() - enqueued_at > s.age_promote then 0      -- short lane, or aged final
       when lane = 'standard' then 1
       else 2 end                                            as lane_rank,    -- overnight last
  user_turn / weight                                         as fair_key      -- weighted round-robin
from q cross join core.settings s
order by lane_rank, fair_key, enqueued_at, job_id, seq;
```

- **Round-robin by user.** `user_turn` numbers a user's queued jobs 1, 2, 3 in order, and everyone's
  turn 1 comes before anyone's turn 2. So A1 B1 C1 A2 A3, not A1 A2 A3 B1 C1.
- **Priority by plan.** `weight` (beta 1, free 1, creator 2, pro 4; eng) divides the turn, so a pro
  user's turn 2 sorts with others' turn 1. Faster, but never exclusive.
- **Shortest-job lanes.** A job whose estimate is ≤ `short_lane_max_s` (eng 20 min) enters the
  `short` lane: previews, stills and most product clips. Finals enter `standard`.
- **No preemption.** A running range is never killed. Ranges are sized to `range_target_s`
  (eng 10 min of GPU), so **a new preview waits at most one range** for a busy GPU. This is how
  previews overtake finals without wasted work.
- **Aging.** A `standard` job waiting longer than `age_promote_s` (eng 45 min) sorts with the short
  lane, so a flood of previews can never starve a final.
- **Overnight lane.** Opt-in, at a discount (eng 40%), with a promise of done-by-next-morning. It is
  claimed only when no short/standard task is ready for that worker, or inside the worker's declared
  idle window. **P1 default for finals on the owner PC.**
- **Stickiness.** Among equal keys a worker prefers the job it just rendered (`last_job_id`), which
  avoids reloading the scene. A pending short-lane task always beats stickiness.
- **Pinning (H3).** `claim_next` skips a render range whose job `pin` does not match the worker's
  `(gpu_model, blender_build, engine_sha)`:
  - The first range claimed sets the job's `pin`.
  - `assets_hash` is fixed at `direct` (GLB sha256 + catalog/asset manifest hash + bake cache keys).
  - A worker missing a cached asset downloads it by hash, never by name.

### 6.3 Claim, lease, heartbeat, resume

- **`claim_next(worker_id)`**:
  - Is one transaction: `select … from runnable_order … for update of tasks skip locked limit 1`,
    filtered by the worker's pools, pin match, `accepting`, not in quiet hours, and lanes not
    paused.
  - Sets `leased` state, `lease_worker` and `lease_expires_at = now() + lease_s` (eng 120 s), and
    bumps `attempts`.
  - Returns the task plus presigned input URLs.
- **`heartbeat(task_id, worker_id)`** every `heartbeat_s` (eng 30 s) extends the lease. It returns
  `cancel: true` when the job was cancelled, so the worker stops within one heartbeat.
- **`report_frames(task_id, worker_id, frames[])`** records frames already uploaded to
  `jobs/<id>/frames/NNNNNN.png`. These are the **resume points**.
- **`reap_leases()`** runs every minute (Cron Trigger). An expired lease goes back to `ready`:
  - Its range is **narrowed to the frames not yet in `frames_done`**.
  - If `attempts ≥ max_attempts` (eng 3), the task fails and the job goes `FAILED` (reservation
    released).
  - A worker that returns after its lease expired finds its token for that task invalid, and its
    `complete` is rejected (`409 lease_lost`). No double writes.
- **Money is independent of attempts.** The charge happens once, from the reservation, when the job
  is `COMPLETE`, with idempotency key `capture:<job_id>`. Retries, resumes and QC re-renders cost the
  house, never the user.

### 6.4 Frame-range splitting (director spec §4.7, H3)

- After `direct`, the API splits `[1, frame_count]` into ranges of
  `ceil(range_target_s / est_s_per_frame)` frames.
  - Rain final at 95 s/frame → 6-frame ranges.
  - Preview at 7 s/frame → 85-frame ranges.
  - Products at 3 s/frame → 200 frames.
- Every range is contiguous (whole ranges, never interleaved frames).
- **One GPU in P1**, so splitting mainly buys preemption points and crash granularity. In P2, the
  ranges of one job fan out to same-pin workers.
- **Bakes (phase 6).** A `bake` task runs once on a CPU worker. Its cache ships to render workers by
  key (`jobs/<id>/bake/<key>/…` or a shared `bake/<key>` store). A render worker never simulates
  (PHASING Phase 7a).
- **Frame QC (director spec §4.8)** runs in `encode`. A failed range re-renders once (house cost);
  a second failure re-rolls the direction (a new job at no charge, linked by `parent_job_id`). QC is
  **report-only until calibrated**, per the director spec.

### 6.5 Position and ETA — "You're #3 · ~12 min"

`queue_status(job_id)` returns `{position, ahead_jobs, eta_start_s, eta_done_s, eta_low_s,
eta_high_s, workers_online, reason}`:

- **position** = 1 + the number of distinct jobs whose first ready task sorts before this job's in
  `runnable_order`, over workers that could run it. It is the same order the GPUs pull in (§4.4).
- **eta_start** = (remaining est of running leases on eligible workers + Σ est of tasks ahead) ÷
  eligible workers accepting now, plus any quiet-hours gap before the first eligible worker wakes.
- **eta_done** = eta_start + this job's own est ÷ the workers it can fan out to.
- **Range.** The low/high band comes from the estimator's spread (§6.6). The UI shows the rounded
  midpoint ("~12 min") and switches to "12–18 min" when the band is wider than ±30%.
- **reason** covers states where a number would lie:
  - `no_worker_online` → "Waiting for a GPU to come online"
  - `quiet_hours_until` → "Starts at 07:00"
  - `lane_overnight` → "Ready by morning"
  - `queue_paused` → "Paused for maintenance"
- **Calibration.** Every job logs predicted vs. actual start and done. `harness`-style calibration
  lands in the register; the UI never claims more precision than the measured error.

### 6.6 Cost model (measured per-block cost, H6)

`estimate(job features, gpu_model)` returns seconds and a spread. It uses the median of the last 20
`cost_samples`, backing off through these keys:

1. `(tier, blocks_sig, gpu_model)`
2. `(tier, world, gpu_model)`
3. `(tier, gpu_model)`
4. the defaults table from §3.

- **Spread** is the inter-quartile range, or ±50% on defaults.
- **Before `direct`**, the blocks are unknown. The estimate uses the chosen world, or the fleet
  median, and is **re-estimated after `direct`**. That re-estimate:
  - moves the job's lane (and so its place) if it crosses `short_lane_max_s`;
  - never changes the frozen quote.
- **Bake-seconds are separate** (PHASING Phase 7c). Money per sample = `gpu_s × worker.hourly_cost_usd
  / 3600`. For the owner PC that is eng electricity: ~0.4 kW × the owner's $/kWh; the default is
  `$0.06/h` until the owner states a rate.
- **Cost-per-clip report** (admin view): the Σ of a job's samples, by block combination, with
  medians per world/effect. It answers director spec §12 Q2 (target price per clip).

### 6.7 Cancel, edit, refund

| Action | While `QUEUED` | While `PREPARING` | While `RENDERING` | After `COMPLETE` |
|---|---|---|---|---|
| Cancel | Full release | Full release | Charge `ceil(price × frames_done / frames)` (eng), release the rest. Frames are deleted. | — (delete the result) |
| Edit (prompt, markers, aspect, world, tier, lane) | Allowed. Re-quote: reserve the delta or release it. Keeps `enqueued_at` (its place). | Cancel + re-enqueue, free | Not allowed ("Cancel and start again") | New job |
| System failure / lease exhaustion / QC double-fail | — | Full release | Full release | — |

- **Released credits come back automatically**, with a ledger row the user can see ("Refunded — the
  render didn't finish").
- **Insufficient credits at edit time** fails the edit and leaves the job unchanged.

### 6.8 Per-user caps (admission control)

- **Active jobs per account:** 1 final + 2 previews in flight (P1). Extends ModVision's
  `MAX_ACTIVE_PER_USER = 1`.
- **Jobs per day per account:** 10 (P1; ModVision's `MAX_DAILY_PER_USER`). Cancelled jobs count,
  so cancel/resubmit loops are capped.
- **Queued GPU-time per account:** at most `max_user_queued_gpu_s` (eng 12 h).
- **Finals per week per beta account:** 3 (eng; §3 capacity).
- **Global admission.** When the predicted wait for a new standard job exceeds 24 h, the API refuses
  it with a plain sentence and offers the overnight lane or a preview.
- Every refusal is a readable sentence, never a code. Caps live in `settings`/`prices`, per plan.

### 6.9 Notifications

- **Finish, fail and "your turn is near"** (seed: position ≤ 1 and ETA < 5 min) go to the `outbox`.
  - **Email** via a transactional provider (Resend recommended; owner-only account). The email
    carries a link to the job page, never the file itself.
  - **Browser notification.** P1 uses the in-page Notification API while any Valora or ModVision
    tab is open (permission asked on the first Render press, with a toggle in Settings). P2 adds Web
    Push through a service worker for closed tabs (VAPID keys generated by us).
- **Opt-out** per channel. **Quiet by default:** one email per job end, never per stage.

---

## 7. Workers

### 7.1 One worker program, pull-only (H1)

`py -m core.worker run` lives in the rendering repo, beside `engine/`, so it imports the engine
directly. Its loop:

1. Claim.
2. Download inputs by presigned URL, verifying sha256.
3. Run the task in a fresh temp dir.
4. Heartbeat on a thread.
5. Upload outputs frame by frame and `report_frames`.
6. `complete` with cost fields, or `fail` with a readable reason.

- **Polling.** Idle polls back off from 5 s to 30 s. The worker opens **no socket for listening**
  (a test asserts it).
- **Task runners** wrap existing seams:
  - `ingest` → `engine.ingest.run.ingest`
  - `direct` → `engine.site_job.direct_site`, with `site_catalog`/`site_rulebook` and the
    `site_deliverable` gate (H4)
  - `render` → `engine.compiler.run.compile_scene(..., frames=[range])`
  - `encode` → the ffmpeg encode, the watermark and the credit line
- ModVision's paint/finish inputs pass through `site_job._paint`.
- **Sandbox (H2):**
  - Blender runs with `--factory-startup --disable-autoexec`.
  - The subprocess env is scrubbed. No worker token, and no Anthropic key except inside `direct` on
    trusted workers.
  - Upload size and polygon limits are re-checked at ingest.
  - The temp dir is deleted after each task.
  - P2 containers are disposable (one task per container lifetime is allowed).

### 7.2 Owner PC = worker #1

- **ON/OFF switch.**
  - Two desktop shortcuts, "Render worker ON" and "Render worker OFF" (the same pattern as the
    MiroFish ON/OFF pair).
  - OFF means **drain**: finish the current range (≤ ~10 min), claim nothing new, then exit.
  - A second OFF within 60 s means stop now; the lease is released and the range returns to the
    queue with its frames kept.
  - The switch state is mirrored to `workers.accepting`, so the ETA shows "Waiting for a GPU to come
    online" honestly.
- **Quiet hours.** These are windows in `workers.quiet_hours`, set in the admin view (or
  `py -m core.worker quiet 23:00-07:00`). No new claim is made inside a window.
- **Yield to the owner.** Before each claim the worker checks `nvidia-smi` for other processes using
  more than eng 1 GB of VRAM. If any, it skips this poll and marks itself `busy_local`. It never
  interrupts a running range.
- **Auto-start** at logon through a Task Scheduler task running as the user. It is not a Windows
  service and needs no admin, and it starts in the state the switch was left in.
- **Identity.** A per-worker token is stored with Windows DPAPI (`py -m core.worker enroll`, which
  takes a one-time enrolment code from the admin view). Rotation and revocation happen in the admin
  view.

### 7.3 Rented GPUs (P2)

- **Provider.** One provider, **one GPU SKU per pool** (H3). Director spec §12 Q1 stays open; the
  candidates are RunPod, Vast.ai and Lambda. The owner picks the account; the plan measures s/frame
  on 2 SKUs before committing.
- **Image.** A pinned container image: Blender 5.0.1 (`engine/blender_pin.py`), the engine at a
  pinned sha, and the worker. Boot runs `core.worker run --pool gpu --exit-when-idle 300`.
- **Autoscaler.** A Cron Trigger every minute computes:
  - `need = ceil(Σ est of ready gpu tasks ÷ wait_target_s)` − (online + booting).
  - It starts or stops pods through the provider API, within `max_pods` and the **daily spend cap**:
    Σ `usd` today + the booting pods' hourly cost × remaining hours ≤ `daily_spend_cap_usd`.
    Hitting the cap sends one admin email and stops scale-up; the queue then drains on owned
    workers.
  - It never scales for the overnight lane alone.
  - Idle pods self-terminate (`--exit-when-idle`), so a lost autoscaler cannot leak spend beyond
    idle-timeout × pods.
- **CPU bake class** (PHASING Phase 7b). Bakes go to cheap CPU pods or the owner PC, never to billed
  GPU time.

---

## 8. Product surfaces

### 8.1 Valora3D (P1 private beta)

- **Services.** `apps/web/lib/services/index.ts` swaps the local stand-ins for cloud implementations
  behind the **same interfaces** (`types.ts`):
  - `SupabaseAuthService`: magic link + invite code. Google comes with the owner's OAuth client.
  - `CloudCreditService`: balance/ledger from RLS reads. `post` is removed from the client; credits
    move only server-side.
  - `CloudRenderService`: `requestPreview`, `requestFinal(target: "cloud")` and `subscribe`, which
    polls `GET /v1/jobs/:id` every 10 s while visible and 60 s while hidden.
  - `projectRepository` stays browser-local in P1. Cloud projects are P2.
- **Deliberate tripwire break.** The `not_connected` assertions (`services.test.ts`, the Playwright
  spec) are **deliberately rewritten** in the same task, because the owner has now asked for the
  wiring. Engine spec §10.2 said this would be a separate, owner-gated step; this spec is that step.
- **Schema widening** (engine spec §10.3/10.4):
  - `RenderJob` gains `position`, `etaS`, `etaLowS`, `etaHighS`, `waitReason`, `lane`,
    `quoteCredits`, `createdAt`, `startedAt`, `finishedAt`, `posterUrl`, `creditLine` and
    `CANCELLED`.
  - `CreditReason` gains `render_charge`, `render_refund` and `beta_grant`.
- **Queue UI** (`JobProgress`, visual-creator pattern, monochrome):
  - A big poster, or the keyframes storyboard (seed, §8.3).
  - One line: **"You're #3 · ~12 min"**, then the stage copy that already exists in
    `JOB_STATUS`.
  - One secondary action, "Cancel" (with the refund sentence), plus a "Notify me" toggle.
  - No gold. The white fill is used once per screen.
- **Login wall stays.** Cloudflare Access remains in front of `valora3d.com` for all of P1, and the
  invite code adds per-person accounts behind it.
- **Admin** at `/admin/queue` (role `admin`):
  - jobs by lane/state with position and ETA;
  - workers with switch, quiet hours, pin, last seen and current task;
  - leases and attempts;
  - today's spend against the cap;
  - cost-per-clip tables;
  - reports.
  - Actions: pause lane/queue, drain worker, cancel+refund, grant credits, revoke worker token,
    promote to showcase. Every action writes `events`.

### 8.2 Valora §2b lane (P1, independent of the core)

This lane is scheduled as a separate P1 lane. It does not touch the queue, so it can start on day 1:

1. **The viewer stops pretending to be the render.** Remove `RainLayer`, the weather in
   `SceneEnvironment`/`Sky`, and every fake "render" effect. The viewer is a brief-writing tool.
2. **Three display modes, Plain by default:**
   - Plain: one matte neutral, monochrome.
   - Material zones: one distinct flat tone per material class. The ids match
     `SubjectProfile.materials[].class`, so a marker `part` string is valid.
   - Final: the model's own materials.
3. **Point-and-describe markers** (director spec §4.2a):
   - Click on the model to drop a numbered pin (max 8), then write a note of 1–280 printable
     characters (the same Unicode rules as the checker).
   - An optional "at 3 s" moment.
   - Anchors are sent in `gltf` space, **inverting the viewer's normalisation** (recentre /
     rescale / rotate). A unit test round-trips a point through `FitCamera`/`sceneScale`.
   - Markers ride in `job.input.markers`.
4. **Showcase gallery from owner-graded renders:**
   - The admin "promote to showcase" flag writes `showcase.json` (R2).
   - The landing `Gallery` reads it, with a variety rule: no two adjacent tiles share a world or
     subject class.
   - Nothing reaches the gallery without the owner's KEEP. Gated on renders existing, so the
     gallery half lands late in P1 or in P2.

### 8.3 ModVision Render Studio (P1: switched to the core)

- **Provider.** `js/render-studio/provider.js` `LocalRenderProvider` is replaced by
  `CoreRenderProvider` with the same method set (`health`, `scenes`, `estimate`, `submit`, `list`,
  `get`, `cancel`, `remove`, `retry`, `fileUrl`, `subscribe`). It targets `render-api` with the
  ModVision Supabase token.
  - The snapshot GLB uploads by presigned PUT (`POST /v1/uploads`), not in the 128 MB JSON body.
  - Still dev-only: the loopback gate stays on the *page*, while the API is remote.
- **Queue UI.** `ui.js` shows the same one-liner and cancel. `QUALITY.final.hint` becomes the
  measured estimate.
- **Retirement.** `tools/render-studio/server.py`'s job queue, `jobs.py` store and `director.py`
  bridge are retired once the cutover passes. No compatibility shim: owner rule.
  - The car gate (`render_cars.py`) moves into the core `licences` table (§9).
  - `watermark.py` moves into the worker's `encode`.
- **Superseded.** `docs/security/2026-09-28-render-videos-bucket.sql` gets a SUPERSEDED header,
  and it is never run.
- **ModVision tenant plan.** `dev` (no credits, the caps above) until ModVision renders are opened
  to users. That is a separate owner decision under the marketing hold.

### 8.4 P1 beta shape

- **Testers.** Invite-only, eng 10–20 testers named by the owner.
- **Credits.** Each gets a `beta_grant` (eng 100 credits) using the existing prices: preview 3,
  cloud final standard 30.
- **Finals.** Overnight lane by default, and 3 finals per week.
- **Watermark.** Every preview is watermarked (server-authoritative, as `jobs.PRESETS` does today).
- **Retention.**
  - Results: 30 days (R2 lifecycle).
  - Frames: 7 days.
  - Uploads: the life of the project, or 30 days after last use.

---

## 9. Licensing

- **The rule.** A ModVision car model may appear in a **user-downloadable video** only if its
  licence evidence permits video export and redistribution of rendered output.
  - Display in the web viewer is not enough; that is the gap `render-denied-cars.json` was made
    for.
- **The licence table.** `core.licences` rows are generated by a ModVision script
  (`scripts/sync-render-licences.mjs`) from the shipping fleet (`print-shipping-cars.mjs`) plus
  per-model evidence in `docs/licensing/`. Each row needs:
  - `allows_video_export`
  - `allows_download`
  - `credit_line`
  - `requires_visible_credit`
  - `evidence_ref`
- **Unknown means no.** A model with no reviewed row is `allows_video_export = false`, which
  replaces today's "fleet minus denylist" default. The sync prints the unknowns for the owner.
- **Checked twice.** `enqueue_job` refuses with "This car's licence does not allow video rendering."
  The worker's `encode` re-checks before upload (belt and braces, like `site_deliverable`).
- **Credit line.** It is stored on the job and written into MP4 metadata (`-metadata
  comment=`/`artist=`). It is shown under the video, on the download page, and in the share text.
  - When `requires_visible_credit` (e.g. CC-BY without another reasonable-manner route), a 1.5 s
    end card is appended in `encode`.
- **Trademarks.**
  - ModVision already has `hide_logos`. The core passes it through.
  - The download page states personal/non-commercial use.
  - Whether brand badges may appear in downloaded videos at all is an **owner/legal decision**
    (§14).
- **Valora uploads.** The user confirms they have the rights (a checkbox per upload, stored with
  the upload sha256). Reported models go on a sha256 denylist checked at upload and enqueue.
- **Engine assets.** Worlds, HDRIs and VDBs are already licence-clean by rule (CC0, owned or
  procedural; `engine/assets/manifest.json` + `CREDITS.md`). Non-CC0 credits join the job's credit
  line automatically.

---

## 10. Abuse and safety

- **Prompt and marker text:**
  - Length ≤ 1000 (prompt; ModVision `MAX_PROMPT`) and ≤ 280 (marker).
  - The Unicode category rules of §4.2a apply to both.
  - A small, versioned blocklist catches obvious slurs and sexual content involving minors, with a
    hard block and a report to the admin.
  - The director's LLM call adds a `policy` verdict field. A refused script fails the job at
    `direct` with a full refund and a plain sentence.
  - Text is always data (H2).
- **Uploads:**
  - GLB magic bytes and a size cap (`MAX_UPLOAD_BYTES` 200 MB).
  - A polygon cap at ingest.
  - The sha256 denylist.
- **Output.** A poster-frame check comes in P2: an NSFW classifier on the poster before a final is
  released.
- **Rate limits:**
  - Per-account caps (§6.8).
  - Per-IP limits on `render-api` via the Workers Rate Limiting binding (eng 60 req/min, 5
    enqueues/min).
  - The invite code gate in P1.
  - Account `suspended` blocks enqueue and refunds queued jobs.
- **Report button** on every result and shared video → `reports` → the admin view (hide, suspend,
  hash-deny).

---

## 11. Payments (P3, owner-gated)

- **Stripe Checkout:**
  - Credit packs (`CREDIT_PACKS` in `pricing.ts`: 100 / $5, 500 / $20, 2000 / $70).
  - Plans (Creator $19/mo, Pro $49/mo) as Stripe subscriptions.
- **Webhook** `POST /v1/stripe/webhook` on `render-api`:
  - Verifies the signature.
  - Posts `ledger` `purchase`/`plan_grant` rows with `idem_key = stripe:<event_id>`, so a replayed
    webhook grants once.
  - Plan changes update `accounts.plan` and `weight`.
- **Refunds and chargebacks** post negative `adjust` rows and can suspend the account.
- **Prices.** The credit prices are re-derived from the cost-per-clip report before launch (director
  spec §12 Q2, engine spec §10.5): a final on the 1024 spp recipe costs far more GPU than
  `cloud_final.standard: 30` credits ($1.50 at the 500-pack rate) implies.
- **Blocked on the owner:** a Stripe account, API keys, a webhook secret, tax settings, and a
  refund policy.

---

## 12. Security summary

| Surface | Control |
|---|---|
| Owner PC / workers | Outbound only; no listener (test); DPAPI-stored worker token; env-scrubbed Blender; factory-startup; temp dir per task |
| `render-api` | The only holder of the Supabase service key and R2 S3 token. Per-tenant CORS allow-list. Every route authenticated. Rate limited. Error bodies are sentences (no stack). |
| Postgres | RLS on every table. Browsers read own rows only. Money/queue mutations only via `security definer` functions with a pinned `search_path`, revoked from `anon`/`authenticated` except the reads they need. Ledger append-only by trigger. |
| R2 | Private bucket. Presigned per-object URLs of 15 min. Keys contain a random job uuid. Lifecycle deletes frames at 7 days. |
| LLM | Key only on trusted workers. Schema-constrained output. Prompt as data. |
| Admin | `role = admin` in `accounts`, checked server-side. Every action in `events`. |
| Secrets in repo | None. `.dev.vars`, worker token files and the DPAPI store are gitignored. A secret-scan runs in the P1 finish task. |

---

## 13. Phased rollout

### P1 — shared core + owner-PC worker + invite-only Valora beta + ModVision switched (full plan)

- **Lane D (DB):** schema, credits, enqueue, the fair-share order, claim/lease/reap, ranges,
  cancel/edit, queue status + ETA, RLS.
- **Lane A (render-api):** auth for both tenants, user routes, worker routes, abuse/rate limits,
  crons (reaper, outbox, rollup).
- **Lane W (worker):** loop, runners on the engine seams, sandbox, cost logging, the owner-PC
  switch/quiet hours/yield, enrolment.
- **Lane V (Valora):** cloud services, queue UI, invites, admin view.
- **Lane V2 (§2b):** no fake effects, three display modes, markers, the showcase gallery (gated on
  grades).
- **Lane M (ModVision):** `CoreRenderProvider`, queue UI, licence sync, delete-account hook,
  retirement of the loopback server's job queue.
- **Exit gate:**
  - A real preview is rendered end to end for both tenants.
  - A worker killed mid-range resumes with one charge.
  - Three-user fairness is proven on a fake worker.
  - The no-inbound test passes.
  - The security review is clean.
  - The owner has invited the first testers.

### P2 — rented GPU farm + autoscale (outline in the plan)

- The provider and SKU are measured and picked (owner account).
- A container image and pinned builds.
- Same-pin fan-out.
- The CPU bake class and bake caches by key.
- The autoscaler with spend cap.
- Web Push.
- The poster NSFW check.
- Cloud projects.
- Realtime job updates.
- A public status line ("GPUs online · typical wait").
- The showcase gallery if not finished.

### P3 — payments + public launch (outline; gated on the owner lifting the marketing hold)

- Stripe.
- Re-priced credits.
- ToS / privacy / refund / acceptable-use pages.
- A DMCA agent.
- Access removed from `valora3d.com` (the login wall becomes the Supabase sign-in).
- Supabase Pro + PITR before real money.
- A load test.
- An `updates` entry.

---

## 14. Owner-only items (accounts, keys, money, legal)

1. **Create the render-core Supabase project** and share its URL, anon key, service-role key and
   database connection string/password (the service key goes only into `render-api` secrets; the
   connection string is used only to apply migrations). Decide Free vs **Pro ($25/mo)**. Pro is
   required before real money (backups/PITR, no pausing).
2. **Cloudflare R2:** create an R2 API token (S3 access key + secret) for presigning. Creating the
   bucket and the `render-api.valora3d.com` route can be done by Claude with the logged-in wrangler.
   The token is a dashboard step, so it goes to the owner or through the owner's Chrome session.
3. **Anthropic API key** for the server-side director (paid usage; cents per job).
4. **Email provider** (Resend or similar): an account, domain DNS verification for `valora3d.com`,
   and an API key. The same SMTP feeds Supabase Auth magic links, since the default SMTP is
   rate-limited.
5. **Google OAuth client** (optional in P1) for "Sign in with Google" on Valora.
6. **Beta invite list** (names/emails), plus the grant size and the weekly finals allowance.
7. **Owner PC worker:** approve the auto-start at logon; set quiet hours; state the electricity
   rate for the cost log.
8. **Licensing:** confirm each shipping car's evidence covers user-downloadable video; approve the
   credit-line format; buy an extended licence where needed; decide on brand badges in downloaded
   videos.
9. **P2 GPU provider:** the account, payment method, API key, the **daily spend cap ($)** and
   `max_pods`; approve the GPU SKU after the 2-SKU measurement.
10. **P3 Stripe:** the account, keys, webhook secret, products/prices, tax settings and payout bank.
11. **Money decisions:** credit prices per tier, plan prices, the free allowance, the overnight
    discount and the per-clip target price (director spec §12 Q2).
12. **Legal (P3):** Terms of Service, privacy policy, refund policy and acceptable-use policy
    approval; DMCA designated-agent registration (US Copyright Office fee).
13. **Grading:** the owner's KEEP on any render before it enters the showcase gallery, and the
    existing golden grades for blocks (H4).
14. **Launch:** lifting the marketing hold (P3 only).

---

## 15. What grew from the seed ("a queue for the GPUs if people are waiting")

- **Keyframes storyboard while you wait.** The engine already has a `keyframes` tier (144p, 4 spp,
  seconds per frame). The trusted worker renders it right after `direct`, so a queued user sees
  their shots in about a minute instead of a spinner. The eng cost is 3 frames. It also lets a user
  cancel a direction they dislike before it costs GPU hours.
- **Preview-first finals.** A final is enqueued *from* a preview (`parent_job_id`), reusing its
  script and seed. The user already approved the shots, so fewer finals are wasted.
- **"Your turn is near" notification**, not just "done".
- **Honest wait reasons**: GPU offline, quiet hours or paused, instead of a fake number (§6.5).
- **Admission control with alternatives.** "The wait is over a day — render overnight at 40% off,
  or make a preview now."
- **Idempotent submit.** A double-click or retry never makes two jobs (`idem_key`).
- **Crash-safe money.** One capture per job regardless of attempts. QC retries at house cost.
- **Stickiness** keeps a GPU on one job's ranges when nobody short is waiting, which saves scene
  reloads.
- **Yield-to-owner** on the owner PC, based on GPU memory, not a timer.
- **Per-block cost feeds pricing.** The admin cost table is the input to director spec §12 Q2.
- **ETA self-calibration.** Predicted vs. actual is logged, so the UI's precision tracks its
  measured error.
- **Showcase promotion** comes out of the admin view, from graded renders, with a variety rule.
- **ModVision + Valora share one variety memory per account**, a later option. P1 keeps them per
  tenant.
- **Public status line and goodwill credits** (seed, P2): if a job finishes more than 2× past its
  quoted ETA, it gets an automatic small credit back. Owner decision, off by default.

---

## 16. Risks

| Risk | Mitigation |
|---|---|
| One owner GPU cannot serve even a small beta's finals (§3) | Finals go to the overnight lane by default, with a weekly finals cap. Previews are the product. P2 farm. The cost report drives the sample-count decision. |
| The ETA is wrong early (no samples) | A wide band shown as a range, with defaults from §3. Calibration register. |
| A render-api or Supabase outage | Workers back off and keep leases short. Jobs are durable in Postgres and nothing is lost. The UI says "Can't reach the render queue — your jobs are safe." |
| A stale worker writes after losing its lease | `complete` checks the lease owner (409). Frame keys are idempotent (same frame, same key). |
| Postgres logic is hard to test on this box (no Docker/psql) | `pgserver` (pip; embedded Postgres) in tests. Fallbacks: a winget PostgreSQL install (one UAC click) or PGlite for single-connection tests (plan Task C1). |
| Licence evidence is incomplete for some cars | Unknown means no (§9). The sync lists unknowns for the owner. |
| The tripwire tests in `apps/web` break | Rewritten deliberately in the wiring task (§8.1), not deleted. |
| Two parallel agents in the rendering checkout | All core work happens in separate worktrees (`rendering-core`, `rendering-valora`), never switching the shared checkout. Paths-only commits. |
