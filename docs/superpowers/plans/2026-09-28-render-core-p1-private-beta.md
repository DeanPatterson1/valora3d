# Render Core P1: shared core, owner-PC worker, invite-only Valora beta, ModVision switched

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal.** Real, invited users of **Valora3D** and the owner's **ModVision Render Studio** can submit a
render, see **"You're #3 · ~12 min"**, get an email and browser notification when it finishes, and
download the video. Credits are reserved at enqueue, charged once on success, and refunded
automatically on cancel or failure. The owner's RTX 5080 PC is worker #1. It pulls work outbound,
has an ON/OFF switch and quiet hours, and opens no port.

**Architecture** (spec §4):

- **Supabase Postgres** holds state. The queue semantics live in SQL functions, and **one**
  `rc_runnable_order` view feeds both the GPUs' claim and the user's position and ETA.
- **Cloudflare R2** holds the blobs.
- **One Cloudflare Worker, `render-api`,** is the only door: both tenants, workers, admin and crons.
- **A Python worker** (`core/worker`) lives in this repo beside `engine/` and wraps the existing
  engine seams:
  - `engine.ingest.run.ingest`
  - `engine.site_job.direct_site`
  - `engine.compiler.run.compile_scene`
  - the `site_catalog` / `site_deliverable` gates

**Tech stack:**

- Postgres 15+ SQL and PL/pgSQL, tested from pytest via `pgserver` (embedded Postgres, pip) and
  `psycopg[binary]` 3.
- TypeScript Cloudflare Worker with Vitest and `@cloudflare/vitest-pool-workers` (Miniflare).
- Python 3.12, stdlib only for the worker runtime (like `tools/render-studio/server.py`), plus
  pytest.
- Valora: Next 16 / React 19 / Zod 4 / Vitest (existing `apps/web`). Read
  `node_modules/next/dist/docs/` before touching Next APIs (`apps/web/AGENTS.md`).
- ModVision: vanilla ES modules and `node --test`.

**Spec:** `docs/superpowers/specs/2026-09-28-render-core-and-queue-design.md`. The numbers in this
plan marked **(eng)** are guesses and go into the calibration register (Task C34).

**Read first:**

- Spec §3–§8.
- Director spec §2b, §4.2a, §4.7, §4.8, §7.
- `engine/site_job.py` (the seam this plan wraps).
- `engine/director/site.py`.
- `apps/web/lib/services/types.ts` on `site/valora3d-preview`.
- `ModVision/tools/render-studio/server.py`, `jobs.py`, `render_cars.py`, `watermark.py`.
- `ModVision/js/render-studio/provider.js`, `ui.js`.

---


## Beta settings (decided 2026-09-28 by Claude; owner delegated: "handle all of it")

These are the P1 defaults every task reads; change them here, not in code.
- **Invites:** the owner's own accounts plus up to 10 single-use invite codes, created from the admin view (C27) and sent by the owner. Cloudflare Access on valora3d.com stays on until P3.
- **Starting credits per invited account:** enough for 20 previews + 3 finals. Finals run in the overnight lane only, max 3 per user per week; previews max 5 per user per day.
- **Owner-PC worker:** auto-starts at logon as the normal user (C17/C34). **No quiet hours by default** (the owner's PC is free for heavy work until ~mid-Dec 2026); the OFF shortcut and yield-to-owner-GPU-use still apply. Revisit at winter break.
- **Electricity for the cost log:** $0.17/kWh (US average, ESTIMATE, labelled as such in the admin view until the owner gives the real rate).
- **Director model:** the latest Claude model, server-side only, key capped by a $20/month workspace limit where the console allows.
- **Cars:** only those with `allowsRenderedVideo: "yes"` in ModVision `data/render-licences.json` can be rendered; each video carries its credit line; badges allowed with a "not affiliated with" line (pending the licence review's recommendation).

## Conventions

- **Never switch branches in `C:\Users\deand\Projects\rendering`.** Another agent works there on
  `renderer/director`. Task C1 creates two worktrees:
  - `C:\Users\deand\Projects\rendering-core` on the new branch `render-core` (from
    `renderer/director`). All `core/` work happens here. Merge `renderer/director` in when the engine
    moves; never rebase it.
  - `C:\Users\deand\Projects\rendering-valora` on `site/valora3d-preview`. All `apps/web` work
    happens here.
  - **Never junction** `node_modules`, `var/`, `assets-in/` or `models/` into a worktree:
    `git worktree remove` follows junctions and empties the source. Run `npm ci` inside the
    worktree instead.
- **ModVision work** happens in `C:\Users\deand\Projects\ModVision` on its current branch, paths-only
  commits. The shared git index is used by other terminals, so run `git diff --cached --name-only`
  before every commit.
- **Commits.**
  - Use `git commit -m "..." -- <paths>`. Never `git add -A`, never `git stash`, never push, never
    touch `main`.
  - Messages end with the two attribution lines given in the session.
- **Python.** Use `py`, never bare `python`.
- **Fast loops:**
  - Core DB + worker: `py -m pytest core/tests -q -m "not pg_concurrency and not live and not blender"`.
  - Core full (chunk gate): `py -m pytest core/tests -q -m "not live"`.
  - API: `npm --prefix core/api test`.
  - Valora: `npm --prefix apps/web test` plus `npm --prefix apps/web run typecheck`.
  - ModVision: `node --test js/render-studio/*.test.js` plus `py -m pytest tools/render-studio -q`.
- **Engine frozen gates still bind.** A core change never edits `engine/` except through a
  merge from `renderer/director`. Before any chunk-end commit, run
  `py -m pytest engine/tests/test_director_floor.py engine/tests/test_director_baseline.py harness/tests/test_baseline_regressions.py -q`.
  It must stay 90/90.
- **Render budget.** Real renders in this plan are **preview tier only** and happen in Task C32,
  after the owner OKs it. Every other test uses a fake `compile_scene` (the same monkeypatch seam
  `engine/__main__.py` documents).
- **No live services in tests.** `live`-marked tests need the owner's keys and are skipped by default.
- **The contract is a file.** `core/contract/v1.json` (JSON Schema for every request and response)
  is written in C2b. Lanes A, W, V and M validate against it in their own tests, so parallel lanes
  cannot drift.
- **UI rules.**
  - Monochrome, with the white fill once per screen and no gold.
  - Visual-creator pattern: pictures, card rows, one CTA, technical controls under a collapsed
    Fine tune.
  - Copy is plain sentences, never codes.

---

## File structure

| Path (worktree) | Create/Modify | Responsibility |
|---|---|---|
| `core/__init__.py` | create | package marker |
| `core/db/migrations/0001_schema.sql` | create (C2) | tables, enums, constraints, append-only trigger |
| `core/db/migrations/0002_credits.sql` | create (C3) | `rc_available`, `rc_reserve`, `rc_capture`, `rc_release` |
| `core/db/migrations/0003_enqueue.sql` | create (C4) | `rc_enqueue_job`, caps, licence check, task graph |
| `core/db/migrations/0004_order.sql` | create (C5) | `rc_runnable_order` view |
| `core/db/migrations/0005_claim.sql` | create (C6) | `rc_claim_next` |
| `core/db/migrations/0006_lease.sql` | create (C7) | `rc_heartbeat`, `rc_report_frames`, `rc_reap_leases` |
| `core/db/migrations/0007_lifecycle.sql` | create (C8) | `rc_split_ranges`, `rc_complete_task`, `rc_fail_task`, `rc_cancel_job`, `rc_edit_job` |
| `core/db/migrations/0008_status.sql` | create (C9) | `rc_estimate`, `rc_queue_status` |
| `core/db/migrations/0009_rls.sql` | create (C10) | RLS policies, grants |
| `core/db/migrate.py` | create (C1) | apply migrations in order, idempotent, records `rc_migrations` |
| `core/tests/conftest.py` | create (C1) | `pg` fixture (pgserver), Supabase `auth` stubs, factories |
| `core/tests/test_*.py` | create | one per migration / worker module |
| `core/contract/v1.json` | create (C2b) | JSON Schema for the API (requests, responses, errors) |
| `core/api/` (`package.json`, `wrangler.jsonc`, `src/*.ts`, `test/*.test.ts`) | create (C11–C16) | the `render-api` Worker |
| `core/worker/__init__.py`, `__main__.py` | create (C17) | `py -m core.worker run|enroll|on|off|quiet|status` |
| `core/worker/config.py`, `identity.py`, `switch.py` | create (C17) | config, GPU/Blender/engine identity, ON/OFF + quiet hours + yield |
| `core/worker/client.py` | create (C18) | stdlib HTTPS client for `/v1/worker/*` |
| `core/worker/loop.py` | create (C18) | claim → run → heartbeat → complete/fail |
| `core/worker/runners.py` | create (C19) | ingest / direct / render / encode runners |
| `core/worker/sandbox.py` | create (C20) | temp dirs, env scrub, Blender flags, size checks |
| `core/worker/cost.py` | create (C21) | GPU/bake/setup seconds + usd per task |
| `core/worker/install.py` | create (C22) | desktop ON/OFF shortcuts, logon task, DPAPI token |
| `apps/web/lib/services/cloud/*` | create (C23) | `SupabaseAuthService`, `CloudCreditService`, `CloudRenderService` |
| `apps/web/lib/schema/project.ts` | modify (C23) | widened `RenderJob`, `CreditReason` |
| `apps/web/components/studio/JobProgress.tsx`, `QueueLine.tsx` | modify/create (C24) | "You're #3 · ~12 min", cancel, notify |
| `apps/web/app/(auth)/invite/page.tsx` | create (C25) | invite-code sign-up |
| `apps/web/app/(app)/admin/queue/page.tsx`, `components/admin/*` | create (C26) | admin queue view |
| `apps/web/components/viewer/*` | modify (C27, C28) | no fake effects, display modes, markers |
| `apps/web/components/landing/Gallery.tsx`, `showcase.ts` | modify/create (C29) | showcase from graded renders |
| `ModVision/js/render-studio/provider.js`, `ui.js`, `config.js` | modify (C30) | `CoreRenderProvider`, queue line |
| `ModVision/scripts/sync-render-licences.mjs` | create (C31) | fleet + licensing evidence → `rc_licences` rows |
| `ModVision/supabase/functions/delete-account/*` | modify (C31) | also deletes the core account |

---

## Parallel map

```
Chunk 0  C1 (worktrees, pg harness, migrate)                               sequential
Chunk 1  C2 ─► C2b (contract) ─► ┬─ C3 ─► C4 ─────────────┐
   (D)                           ├─ C5 ─► C6 ─► C7 ─► C8 ─┼─► C9
                                 └─ C10 (after C4 tables) ─┘
Chunk 2  (A) after C2b:  C11 ─► C12 ─► (C13 ║ C14 ║ C15) ─► C16
Chunk 3  (W) after C2b:  C17 ─► C18 ─► (C19 ║ C20 ║ C21) ─► C22
Chunk 4  (V) after C2b:  C23 ─► (C24 ║ C25 ║ C26)
         (V2, day 1, independent): (C27 ║ C28) ─► C29 [gallery half gated on owner grades]
         (M) after C2b:  C30 ─► C31
Chunk 5  C32 (end-to-end, owner-OK preview renders) ─► C33 (security review) ─► C34 (deploy + beta + register)
```

- Lanes **A, W, V and M** build against the contract with fakes, so they run fully in parallel with
  lane D after C2b.
- **Lane V2** (spec §8.2) needs nothing from the core and can start immediately.
- **Recommended order when lanes can't all run:** D → W → A → M → V → V2. This proves the queue on
  the owner's own studio first, and it proves the loop before the beta UI.

---

## Chunk 0: Gate and harness

### Task C1: Worktrees, embedded Postgres test harness, migration runner

**Files:**
- Create: `core/__init__.py`, `core/db/__init__.py`, `core/db/migrate.py`, `core/tests/__init__.py`,
  `core/tests/conftest.py`, `core/tests/test_migrate.py`, `core/requirements-dev.txt`
- Modify: `pytest.ini` or `pyproject.toml` (whichever the repo uses; read first) — register the
  markers `pg`, `pg_concurrency`, `live`, `blender`

- [ ] **Step 1: Worktrees** (from `C:\Users\deand\Projects\rendering`, which stays on its branch):

```bash
git worktree add -b render-core ../rendering-core renderer/director
git worktree add ../rendering-valora site/valora3d-preview
```

  Then `cd ../rendering-valora/apps/web && npm ci`. **No junctions.**
- [ ] **Step 2: Pick the Postgres engine.** `py -m pip install pgserver "psycopg[binary]>=3.2"`, then
  run the probe `py -c "import pgserver,tempfile;s=pgserver.get_server(tempfile.mkdtemp());print(s.psql('select version();'))"`.
  - **Expected:** a `PostgreSQL 16.x` banner.
  - **Fallback 1:** `winget install PostgreSQL.PostgreSQL.17`. This needs one UAC click, which is
    the owner's. Then point `RC_TEST_PG_BIN` at its `bin`.
  - **Fallback 2:** PGlite via node, single connection. `pg_concurrency` tests are then skipped
    with a reason printed.
  - Write the choice into the Task C34 register.
- [ ] **Step 3: Failing test** `core/tests/test_migrate.py`:

```python
import pytest
from core.db.migrate import migrate, MIGRATIONS_DIR

pytestmark = pytest.mark.pg


def test_migrate_is_idempotent_and_ordered(pg):
    first = migrate(pg.uri)
    second = migrate(pg.uri)
    assert first == sorted(first) and first, "applies every file in name order"
    assert second == [], "a second run applies nothing"
    with pg.connect() as c:
        rows = c.execute("select name from rc_migrations order by name").fetchall()
    assert [r[0] for r in rows] == first


def test_auth_stub_reads_jwt_sub(pg):
    with pg.connect() as c:
        c.execute("select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000001', true)")
        assert str(c.execute("select auth.uid()").fetchone()[0]).endswith("1")
```

- [ ] **Step 4: Run.** Expected: FAIL (no module).
- [ ] **Step 5: Implement.**
  - **`conftest.py`, the session `pg` fixture:**
    - A `pgserver` data dir under `tmp_path_factory`.
    - Creates the Supabase-shaped `auth` schema stub: `auth.users(id uuid pk, email text)` and
      `auth.uid()` reading `current_setting('request.jwt.claim.sub', true)::uuid`.
    - Creates the roles `anon`, `authenticated`, `service_role` (nologin).
    - Applies migrations once.
  - **Per test:** a function-scoped `db` fixture opens a transaction and rolls it back.
    `pg_concurrency` tests use a fresh database per test instead.
  - **Factories:** `make_account(tenant, plan, weight)`, `make_worker(pools, gpu_model,
    trusted)`, `grant(account, credits)`.
  - **`migrate.py`:**
    - Reads `core/db/migrations/*.sql` in name order.
    - Each file runs in one transaction with `rc_migrations(name, sha256, applied_at)`.
    - A changed sha256 on an applied file raises `MigrationDrift` (never silently re-run).
    - CLI: `py -m core.db.migrate --url $RC_DB_URL`.
- [ ] **Step 6: Run** `py -m pytest core/tests/test_migrate.py -q`. Expected: PASS.
- [ ] **Step 7: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(core): worktree, embedded Postgres harness and migration runner (render-core C1)" -- core/__init__.py core/db core/tests/__init__.py core/tests/conftest.py core/tests/test_migrate.py core/requirements-dev.txt pytest.ini
```

---

## Chunk 1 (lane D): The database is the queue

### Task C2: Schema (tables, constraints, append-only ledger)

**Files:** Create `core/db/migrations/0001_schema.sql`, `core/tests/test_schema.py`

- [ ] **Step 1: Failing tests** (`core/tests/test_schema.py`, marker `pg`):

```python
import pytest, psycopg

pytestmark = pytest.mark.pg


def test_ledger_is_append_only(db, make_account, grant):
    a = make_account("valora", "beta")
    grant(a, 100, idem="g1")
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        db.execute("update rc_ledger set amount = 1000 where account_id = %s", (a,))
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        db.execute("delete from rc_ledger where account_id = %s", (a,))


def test_ledger_idem_key_is_unique(db, make_account, grant):
    a = make_account("valora", "beta")
    grant(a, 100, idem="g1")
    with pytest.raises(psycopg.errors.UniqueViolation):
        grant(a, 100, idem="g1")


def test_job_states_and_lanes_are_closed_sets(db, make_account):
    a = make_account("valora", "beta")
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("insert into rc_jobs (account_id, tenant, kind, lane, state, input, quote_credits, idem_key)"
                   " values (%s,'valora','preview','fast','QUEUED','{}',3,'k')", (a,))


def test_task_range_is_well_formed(db, job_factory):
    j = job_factory()
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("insert into rc_tasks (job_id, seq, kind, pool, state, frame_start, frame_end)"
                   " values (%s, 9, 'render', 'gpu', 'ready', 10, 5)", (j,))


def test_accounts_unique_per_tenant(db, make_account):
    make_account("valora", "beta", external="u1")
    make_account("modvision", "dev", external="u1")          # same external id, other tenant: fine
    with pytest.raises(psycopg.errors.UniqueViolation):
        make_account("valora", "beta", external="u1")
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** `0001_schema.sql` exactly as spec §5, using the `rc_` prefix:
  - `rc_tenants`, `rc_accounts`, `rc_invites`, `rc_ledger`, `rc_reservations`, `rc_prices`,
    `rc_jobs`, `rc_tasks`, `rc_workers`, `rc_cost_samples`, `rc_licences`, `rc_outbox`,
    `rc_reports`, `rc_events`, `rc_settings`.
  - `check` constraints for every closed set:
    - job `state` ∈ `QUEUED|PREPARING|RENDERING|ENCODING|UPLOADING|COMPLETE|FAILED|CANCELLED`;
    - `lane` ∈ `short|standard|overnight`;
    - `kind` ∈ `preview|final|stills`;
    - task `kind` and `state`;
    - `pool` ∈ `trusted|gpu|cpu`.
  - `frame_start <= frame_end`, and `frames_done int[] not null default '{}'`.
  - The `rc_ledger_append_only()` trigger raises `append-only ledger` on UPDATE and DELETE.
  - Seed `rc_tenants` (`valora`, `modvision`) and one `rc_settings` row with every (eng) value from
    spec §5 settings. Seed `rc_prices` from `apps/web/lib/pricing.ts` `CREDIT_COSTS`:
    - preview 3;
    - final standard 30, high 60, ultra 90, 4k 160;
    - overnight = ⌈0.6 × standard⌉ (eng).
  - Index: `rc_tasks (state, pool)` where `state = 'ready'`; `rc_jobs (account_id, enqueued_at)`.
- [ ] **Step 4: Run.** Expected: PASS. **Step 5: Commit**
  (`feat(core): render-core schema (C2)` -- `core/db/migrations/0001_schema.sql core/tests/test_schema.py core/tests/conftest.py`).

### Task C2b: The API contract file

**Files:** Create `core/contract/v1.json`, `core/tests/test_contract.py`

- [ ] **Step 1: Failing test.** The contract validates the example documents it embeds (every
  schema carries `examples`). Each job-state name equals the SQL check set (read from
  `0001_schema.sql` by regex). `RenderJob.status` values equal Valora's `RenderJobStatus` plus
  `CANCELLED`.
- [ ] **Step 2: Implement** `v1.json` (JSON Schema 2020-12). It covers these definitions:
  - `Job`: id, kind, lane, status, position, etaS, etaLowS, etaHighS, waitReason, quoteCredits,
    frame, totalFrames, createdAt, startedAt, finishedAt, posterUrl, resultUrl, creditLine,
    error.
  - `EnqueueRequest`: kind, tier, lane, prompt ≤ 1000, markers (the director §4.2a schema,
    copied), aspect, world, durationS, paint, finish, uploadKey, uploadSha256, modelKey,
    idemKey, notify.
  - `EditRequest`.
  - `QueueStatus`.
  - `Upload` (presign) request and response.
  - `WorkerClaim` response: task, inputs as `{name: {url, sha256}}`, outputs as
    `{name: putUrl}`, heartbeatS, leaseS.
  - `Heartbeat` response: `{cancel: bool, leaseExpiresAt}`.
  - `FramesReport`.
  - `Complete`, with cost fields `gpuS`, `bakeS`, `setupS` and `blocksSig`.
  - `Fail`: `{retryable, userMessage, detail}`.
  - `Error`: `{error: "<plain sentence>", code}`.

  Endpoints are listed under `x-routes`, one entry per route.
- [ ] **Step 3: Run, commit** (`docs(core): API contract v1 (C2b)`).

### Task C3: Credits — reserve, capture once, release [parallel with C5, C10]

**Files:** Create `core/db/migrations/0002_credits.sql`, `core/tests/test_credits.py`

- [ ] **Step 1: Failing tests:**

```python
import pytest
pytestmark = pytest.mark.pg


def available(db, a):
    return db.execute("select rc_available(%s)", (a,)).fetchone()[0]


def test_reserve_holds_and_available_drops(db, make_account, grant, job_factory):
    a = make_account("valora", "beta"); grant(a, 100)
    j = job_factory(account=a, quote=30)
    db.execute("select rc_reserve(%s)", (j,))
    assert available(db, a) == 70


def test_reserve_refuses_when_short(db, make_account, grant, job_factory):
    a = make_account("valora", "beta"); grant(a, 10)
    j = job_factory(account=a, quote=30)
    with pytest.raises(Exception, match="You need 30 credits but have 10"):
        db.execute("select rc_reserve(%s)", (j,))


def test_capture_is_once_even_if_called_twice(db, make_account, grant, job_factory):
    a = make_account("valora", "beta"); grant(a, 100)
    j = job_factory(account=a, quote=30); db.execute("select rc_reserve(%s)", (j,))
    db.execute("select rc_capture(%s, null)", (j,))
    db.execute("select rc_capture(%s, null)", (j,))          # a retried completion
    assert available(db, a) == 70
    n = db.execute("select count(*) from rc_ledger where job_id = %s and kind = 'capture'", (j,)).fetchone()[0]
    assert n == 1


def test_partial_capture_releases_the_rest(db, make_account, grant, job_factory):
    a = make_account("valora", "beta"); grant(a, 100)
    j = job_factory(account=a, quote=30); db.execute("select rc_reserve(%s)", (j,))
    db.execute("select rc_capture(%s, 10)", (j,))            # cancelled a third of the way through
    assert available(db, a) == 90


def test_release_after_capture_is_a_noop(db, make_account, grant, job_factory):
    a = make_account("valora", "beta"); grant(a, 100)
    j = job_factory(account=a, quote=30); db.execute("select rc_reserve(%s)", (j,))
    db.execute("select rc_capture(%s, null)", (j,)); db.execute("select rc_release(%s)", (j,))
    assert available(db, a) == 70
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - **`rc_available(account)`** = Σ `rc_ledger.amount` − Σ `rc_reservations.amount` where
    `status = 'held'`.
  - **`rc_reserve(job)`:**
    - Locks the account row (`for update`) so two enqueues cannot overspend.
    - Raises the user sentence `You need N credits but have M.` (errcode `PT402`).
  - **`rc_capture(job, amount null=all)`:**
    - Only from `held`.
    - Inserts ledger `-amount` with `idem_key = 'capture:'||job`.
    - Sets `captured`, and `partial` when amount < reserved.
  - **`rc_release(job)`:** only from `held`; sets `released`. A release is not a ledger movement
    (nothing was taken). A **refund** row is used only when credits already captured are returned
    by an admin (`kind='refund'`, `idem_key='refund:'||job`).
  - All are `security definer`, with `set search_path = public`, revoked from `anon` and
    `authenticated`.
- [ ] **Step 4: Run, commit.**

### Task C4: `rc_enqueue_job` — caps, licence, quote, task graph

**Files:** Create `core/db/migrations/0003_enqueue.sql`, `core/tests/test_enqueue.py`

- [ ] **Step 1: Failing tests** (each asserts the exact user sentence):
  - `test_enqueue_reserves_quote_and_creates_ingest_and_direct_tasks`:
    - state `QUEUED`;
    - two tasks (`ingest` ready, `direct` blocked), both pool `trusted`;
    - reservation `held`;
    - `quote_credits` from `rc_prices` for (tenant, plan, tier, lane).
  - `test_same_idem_key_returns_the_first_job`: a double-click makes one job and one reservation.
  - `test_active_cap`: a second final while one is in flight gives "You already have a final
    render in progress."; a third preview gives the preview sentence.
  - `test_daily_cap_counts_cancelled`: 10 jobs today, 5 of them cancelled; the 11th gives "You've
    reached today's limit of 10 renders."
  - `test_weekly_finals_cap_for_beta` (3).
  - `test_queued_gpu_time_cap` (`max_user_queued_gpu_s`).
  - `test_licence_unknown_means_no` (tenant `modvision`, `modelKey` with no `rc_licences` row) gives
    "This car's licence does not allow video rendering."
  - `test_licence_allowed_sets_credit_line_on_job`.
  - `test_suspended_account_cannot_enqueue`.
  - `test_queue_paused_refuses_with_sentence`.
  - `test_lane_from_estimate`:
    - a preview whose `est_gpu_s` ≤ `short_lane_max_s` goes to `short`;
    - a final goes to `standard`, unless `lane='overnight'` was asked;
    - a beta final with no lane asked defaults to `overnight` (spec §8.4, a setting).
  - `test_global_admission_offers_overnight`: when the predicted wait for a new standard job is over
    24 h, the call raises "The wait is over a day. Render overnight or make a preview now."
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** `rc_enqueue_job(account, input jsonb, idem_key) returns uuid`:
  1. idem lookup;
  2. account status;
  3. `queue_paused`;
  4. caps (the counts use `rc_jobs` with `created_at >= date_trunc('day', now() at time zone
     'utc')`);
  5. the licence row;
  6. `rc_estimate` (C9 provides it; until then a stub returns the §3 defaults, replaced in C9);
  7. lane;
  8. quote;
  9. insert job;
  10. `rc_reserve`;
  11. insert tasks;
  12. `rc_events`.

  It is one transaction.
- [ ] **Step 4: Run, commit.**

### Task C5: `rc_runnable_order` — fair share, lanes, weights, aging, stickiness [parallel with C3, C10]

**Files:** Create `core/db/migrations/0004_order.sql`, `core/tests/test_order.py`

- [ ] **Step 1: Failing tests.** Build ready tasks directly: `ready_task(account, lane,
  enqueued_at)`. The helper `order(db)` returns `[(user_label, job_label)]` from the view.

```python
import pytest
from datetime import timedelta
pytestmark = pytest.mark.pg


def test_round_robin_by_user_not_fifo_by_job(db, scenario):
    s = scenario(A=["a1", "a2", "a3"], B=["b1"], C=["c1"], lane="standard")   # A enqueued first, all three
    assert s.order() == ["a1", "b1", "c1", "a2", "a3"]


def test_weight_lets_pro_take_two_turns_per_round(db, scenario):
    s = scenario(P=["p1", "p2", "p3"], F=["f1", "f2"], weights={"P": 2, "F": 1}, lane="standard")
    assert s.order()[:4] == ["p1", "p2", "f1", "p3"]          # p2 has turn 2/2 = 1.0, ties with f1, earlier enqueue wins


def test_short_lane_overtakes_standard(db, scenario):
    s = scenario(A=["final1"], lane="standard")
    s.add(B=["preview1"], lane="short", later=timedelta(minutes=5))
    assert s.order() == ["preview1", "final1"]


def test_aged_standard_is_promoted(db, scenario, settings):
    s = scenario(A=["final1"], lane="standard", ago=settings.age_promote + timedelta(minutes=1))
    s.add(B=["preview1"], lane="short")
    assert s.order() == ["final1", "preview1"]                # enqueued earlier, same lane rank now


def test_overnight_is_last(db, scenario):
    s = scenario(A=["night1"], lane="overnight", ago=timedelta(hours=5))
    s.add(B=["final1"], lane="standard")
    assert s.order() == ["final1", "night1"]


def test_cancelled_jobs_vanish_and_do_not_hold_a_turn(db, scenario):
    s = scenario(A=["a1", "a2"], B=["b1"], lane="standard")
    s.cancel("a1")
    assert s.order() == ["a2", "b1"]
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the view as in spec §6.2:
  - `user_turn = dense_rank() over (partition by account_id order by enqueued_at, job_id)`, over
    jobs that still have ready or leased tasks. A job whose earlier ranges are leased still holds
    its turn, so a user's second job does not jump ahead.
  - `fair_key = user_turn::numeric / weight`.
  - `lane_rank` with the `age_promote_s` promotion.
  - Order by `lane_rank, fair_key, enqueued_at, job_id, seq`.
  - **Stickiness is not in the view.** It is a claim-time tie-break (C6), so a user's visible
    position never depends on which GPU last ran what.
- [ ] **Step 4: Run, commit.**

### Task C6: `rc_claim_next` — SKIP LOCKED, pools, pin, switch, quiet hours

**Files:** Create `core/db/migrations/0005_claim.sql`, `core/tests/test_claim.py`,
`core/tests/test_claim_concurrency.py`

- [ ] **Step 1: Failing tests:**
  - `test_claims_first_in_order_for_matching_pool`: a `gpu` worker never gets `trusted` tasks.
    An untrusted worker never gets `direct`.
  - `test_not_accepting_worker_gets_nothing`.
  - `test_quiet_hours_get_nothing`:
    - tz-aware;
    - a window crossing midnight (`23:00-07:00`);
    - tested with `set_config('rc.now', …)`. Every function reads `rc_now()`, which defaults to
      `now()`, so tests can move the clock.
  - `test_paused_lane_is_skipped`.
  - `test_pin_set_on_first_render_range_and_enforced` (H3): worker X (RTX 5080, 5.0.1, sha1) claims
    range 1, so the job pin is set. Worker Y (RTX 4090) gets nothing from that job. Worker Z (same
    triple) gets range 2.
  - `test_engine_sha_mismatch_skips_render_but_not_other_jobs`.
  - `test_stickiness_prefers_last_job_when_no_short_waiting`.
  - `test_short_task_beats_stickiness`.
  - `test_claim_sets_lease_attempts_and_job_state`: the job becomes `PREPARING` for ingest/direct
    and `RENDERING` for render, with `started_at` set once.
- [ ] **Concurrency test** (`pg_concurrency`): 8 threads, each with its own connection and worker,
  loop `rc_claim_next` against 200 ready tasks. Assert every task is claimed exactly once and no
  thread got an error.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** `rc_claim_next(worker uuid) returns setof rc_tasks`:

```sql
-- core of the function (plan-level sketch; tests are the spec)
select t.id into v_task
from rc_runnable_order o
join rc_tasks t on t.id = o.task_id
join rc_jobs  j on j.id = o.job_id
where o.pool = any(v_worker.pools)
  and (o.kind <> 'direct' or v_worker.trusted)
  and not rc_lane_paused(o.lane)
  and (o.kind <> 'render' or j.pin is null or rc_pin_matches(j.pin, v_worker))
order by o.lane_rank,
         (o.lane_rank = 0) desc,                                  -- nothing beats a waiting short task
         case when o.job_id = v_worker.last_job_id then 0 else 1 end,
         o.fair_key, o.enqueued_at, o.job_id, o.seq
for update of t skip locked
limit 1;
```

  - Gate the whole thing on `v_worker.accepting and not rc_in_quiet_hours(v_worker)` and not
    `queue_paused`.
  - Then update the task (lease, attempts), job (state, pin on the first render,
    `started_at`) and worker (`state='busy'`, `last_job_id`, `last_seen`), and write
    `rc_events`.
- [ ] **Step 4: Run** both files. **Step 5: Commit.**

### Task C7: Heartbeat, frame reports, lease reaper (crash → resume, no double work)

**Files:** Create `core/db/migrations/0006_lease.sql`, `core/tests/test_lease.py`

- [ ] **Step 1: Failing tests:**

```python
def test_heartbeat_extends_lease_and_reports_cancel(db, claimed_render):
    t, w = claimed_render(frames=(1, 12))
    r = db.execute("select * from rc_heartbeat(%s, %s)", (t, w)).fetchone()
    assert r.cancel is False
    db.execute("select rc_cancel_job(%s, 'user')", (claimed_render.job,))
    assert db.execute("select cancel from rc_heartbeat(%s, %s)", (t, w)).fetchone()[0] is True


def test_heartbeat_from_wrong_worker_is_lease_lost(db, claimed_render, make_worker):
    t, w = claimed_render(frames=(1, 12))
    with pytest.raises(Exception, match="lease_lost"):
        db.execute("select rc_heartbeat(%s, %s)", (t, make_worker(["gpu"])))


def test_reaper_returns_expired_range_narrowed_to_unfinished_frames(db, claimed_render, clock):
    t, w = claimed_render(frames=(1, 12))
    db.execute("select rc_report_frames(%s, %s, %s)", (t, w, [1, 2, 3, 4, 5]))
    clock.advance(seconds=200)                                       # lease_s 120 (eng)
    db.execute("select rc_reap_leases()")
    row = db.execute("select state, frame_start, frame_end, frames_done from rc_tasks where id=%s", (t,)).fetchone()
    assert row == ("ready", 1, 12, [1, 2, 3, 4, 5])                  # range kept; the worker skips done frames


def test_reaper_fails_job_and_releases_after_max_attempts(db, claimed_render, clock, available):
    ...  # 3 expiries -> task failed, job FAILED, reservation released, outbox has a 'failed' email


def test_complete_after_lease_lost_is_rejected(db, claimed_render, clock, make_worker):
    ...  # expired + re-claimed by worker 2; worker 1's rc_complete_task raises lease_lost


def test_report_frames_is_idempotent_and_sorted(db, claimed_render):
    ...  # reporting [3,1,3] then [2] gives {1,2,3}
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement:**
  - `rc_heartbeat(task, worker) returns (cancel bool, lease_expires_at timestamptz)`.
  - `rc_report_frames(task, worker, int[])`: a sorted union, frames inside the range only.
  - `rc_reap_leases()`: returns the count. On the final attempt it calls `rc_fail_job` (C8), which
    releases the reservation and queues the outbox row. Workers are marked `off` when
    `last_seen` is older than 3 × heartbeat.
  - **Resume granularity is one frame.** The worker skips `frames_done` (C19).
- [ ] **Step 4: Run, commit.**

### Task C8: Ranges, completion, failure, cancel, edit (the money rules of spec §6.7)

**Files:** Create `core/db/migrations/0007_lifecycle.sql`, `core/tests/test_lifecycle.py`

- [ ] **Step 1: Failing tests:**
  - **`rc_split_ranges(job, frame_count, est_s_per_frame)`** after `direct`:
    - range size = `ceil(range_target_s / est_s_per_frame)`;
    - 300 frames at 95 s gives 6-frame ranges (50 ranges);
    - at 7 s gives 86-frame ranges (4 ranges);
    - ranges are contiguous and cover `[1, N]` exactly once;
    - an `encode` task is created blocked on all of them.
  - **The direct stage re-estimates**, and the job may change lane. `quote_credits` is unchanged
    (the frozen quote).
  - **`rc_complete_task`:**
    - unblocks children;
    - on the `encode` completion the job goes `COMPLETE`, `rc_capture(job, null)` runs once, an
      outbox `done` email is queued, and a `rc_cost_samples` row is written per task from the
      completion's cost fields.
  - **The full crash-resume story (the headline test):**
    1. enqueue;
    2. run ingest and direct;
    3. claim range 1 and report 3 of 6 frames;
    4. expire;
    5. re-claim by another same-pin worker;
    6. complete all tasks.

    Assert:
    - exactly one `capture` ledger row;
    - `available == grant − quote`;
    - `attempts == 2` on that task;
    - the other ranges have `attempts == 1`.
  - **`rc_fail_task(retryable=true)`** returns the task to `ready` until `max_attempts`.
    `retryable=false` fails the job now; the job gets `error_user` and the reservation is released.
  - **Cancel matrix** (spec §6.7):
    - queued → released in full;
    - preparing → released in full;
    - rendering with 30 of 300 frames done → captures `ceil(30 × 0.1) = 3`, the rest released, and
      the leased task's next heartbeat returns cancel;
    - complete → refused with "This render is finished. Delete it instead."
  - **Edit:**
    - queued, a prompt change → same `enqueued_at`, input replaced, re-quoted with the delta
      reserved;
    - an edit to a pricier tier with insufficient credits → refused and the job unchanged;
    - an edit while `RENDERING` → "Cancel and start again to change a render that has started."
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the six functions. Every state change writes `rc_events`.
- [ ] **Step 4: Run, commit.**

### Task C9: Estimator and `rc_queue_status` — "You're #3 · ~12 min"

**Files:** Create `core/db/migrations/0008_status.sql`, `core/tests/test_status.py`

- [ ] **Step 1: Failing tests:**
  - **`rc_estimate(features jsonb, gpu_model)` backs off by key:**
    1. `(tier, blocks_sig, gpu)`, with ≥ 5 samples;
    2. `(tier, world, gpu)`;
    3. `(tier, gpu)`;
    4. the defaults (preview 7 s/f, final 95 s/f, setup 60 s; spec §3).

    It returns `{s_per_frame, setup_s, spread}`: the IQR over samples, ±50% on defaults.
  - **Position counts distinct jobs, not tasks:** a user behind 1 final (50 ranges) and 1 preview
    is `#3`.
  - **Position respects fairness:** with A1 A2 A3 queued, B enqueues one job after them and is `#2`.
  - **ETA arithmetic:**
    - 2 workers online;
    - ahead = 1 running task with 300 s left + 1200 s queued;
    - own 600 s;
    - `eta_start = (300 + 1200) / 2 = 750`, `eta_done = 750 + 600 = 1350`.
  - **Wait reasons:**
    - no accepting worker → `reason='no_worker_online'`, `eta_start_s is null`;
    - all eligible workers in quiet hours until 07:00 → `quiet_hours_until` with the timestamp,
      and the ETA adds the gap;
    - overnight lane → `lane_overnight`;
    - paused → `queue_paused`.
  - **Pin-aware:** a job pinned to RTX 5080 does not count RTX 4090 workers as capacity.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** both. Replace C4's estimate stub. `rc_queue_status(job)` reads
  `rc_runnable_order` **only**, so the position is literally claim order (spec §4.4). It returns the
  contract's `QueueStatus`.
- [ ] **Step 4: Run** the whole lane-D suite plus the concurrency file. **Step 5: Commit.**

### Task C10: RLS, grants, admin role [parallel with C3/C5 once C2 lands]

**Files:** Create `core/db/migrations/0009_rls.sql`, `core/tests/test_rls.py`

- [ ] **Step 1: Failing tests** run as `set local role authenticated` with a JWT `sub`:
  - A user sees own `rc_jobs`, `rc_ledger` and `rc_reservations` only. Another user's rows read as
    zero rows (not an error).
  - A user cannot insert or update `rc_jobs`, `rc_ledger` or `rc_tasks` directly (permission
    denied).
  - `anon` sees nothing.
  - A user cannot execute `rc_claim_next`, `rc_capture`, `rc_reserve` or `rc_reap_leases`.
  - A user can execute `rc_queue_status` only for an own job; another's gives "not found".
  - A `modvision` account row is invisible to Valora's auth: `external_user_id` must equal
    `auth.uid()` **and** the tenant must be `valora`. ModVision users never read Postgres
    directly; they go through `render-api`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Enable RLS on every table, then `revoke all … from anon, authenticated`.
  - Grant only the owner-select policies above.
  - Every `rc_*` function is `security definer`, with `search_path` pinned and `revoke execute …
    from public`.
  - Grant `service_role` everything.
- [ ] **Step 4: Run** the full lane-D suite. **Commit.**

---

## Chunk 2 (lane A): `render-api`, the only door

**Shared setup** for C11–C16:

- `core/api` is its own npm package. `wrangler.jsonc` defines:
  - name `render-api`;
  - route `render-api.valora3d.com` (custom domain; added at deploy in C34);
  - an R2 binding `BLOBS` → bucket `render-core`;
  - a Rate Limiting binding;
  - crons `* * * * *`.
- Secrets (never in the repo; `.dev.vars` gitignored):
  - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`;
  - `MODVISION_SUPABASE_URL`, `MODVISION_ANON_KEY`;
  - `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`;
  - `RESEND_API_KEY` (optional).
- **Postgres access** goes only through PostgREST RPC (`POST /rest/v1/rpc/rc_*`) with the service
  key, wrapped in `src/db.ts`. Tests use a `FakeDb` that records the calls and replays fixtures, and
  every fixture is validated against `core/contract/v1.json`.

### Task C11: Skeleton, routing, CORS per tenant, error envelope

- [ ] **Failing tests** (`test/app.test.ts`):
  - `GET /v1/health` gives `{ok:true, version}`.
  - Unknown route gives 404 `{error:"Not found."}`.
  - An OPTIONS preflight from `https://valora3d.com` is allowed. From `http://localhost:8080` it is
    allowed only for the `modvision` tenant header. From `https://evil.example` there is no
    `Access-Control-Allow-Origin`.
  - A thrown error never leaks a stack: the body is always `{error: <sentence>, code}`.
- [ ] **Implement:**
  - `src/index.ts` with a tiny router (no framework).
  - `src/cors.ts` reads `rc_tenants.allowed_origins`, cached 60 s.
  - `src/errors.ts`.
- [ ] Run `npm --prefix core/api test`, then commit.

### Task C12: Auth adapters — Valora (core Supabase), ModVision (remote `/auth/v1/user`), workers

- [ ] **Failing tests:**
  - A Valora bearer is verified with the core project's `/auth/v1/user` (the same adapter as
    ModVision, but a different base), so there is no JWT library.
  - The result is cached by SHA-256 of the token for 60 s, and rejections are not cached. This
    mirrors `SupabaseAuth` in `ModVision/tools/render-studio/server.py`; port its tests.
  - A 401 from Supabase gives "Your sign-in has expired. Sign in again to render videos."
  - A 5xx gives 503 with "The sign-in service could not check your account. Try again shortly."
  - Account upsert on first sight: `(tenant, external_user_id)` → `rc_accounts`. A Valora account
    requires a consumed invite (C25), else 403 "Valora is invite-only right now."
  - Worker auth:
    - `Authorization: Worker <id>.<secret>`;
    - SHA-256 of the secret is compared in constant time with `rc_workers.token_hash`;
    - a revoked worker gets 401;
    - worker routes reject user tokens and vice versa.
  - The admin check is `rc_accounts.role = 'admin'`, looked up server-side.
- [ ] **Implement** `src/auth.ts`. **Commit.**

### Task C13: User routes [parallel with C14, C15]

- [ ] **Failing tests**, one per route. Each response validates against the contract.
  - **`POST /v1/uploads`** `{sha256, bytes, contentType}`:
    - checks `bytes ≤ 200 MB` (`MAX_UPLOAD_BYTES`), GLB content type only, and the sha256 denylist;
    - returns a presigned R2 PUT for `uploads/<accountId>/<sha256>.glb`, 15 min, with the
      sha256 checksum header required;
    - an existing object returns `{exists:true}` (dedupe).
  - **`POST /v1/jobs`:**
    - runs the abuse filter (C15);
    - checks that the upload object exists and its size;
    - calls `rc_enqueue_job`;
    - returns `Job` with the queue status;
    - maps the SQL `PT4xx` errors to their sentences with 402, 403, 409 or 429;
    - the same `idemKey` twice returns the same job.
  - **`GET /v1/jobs`:** the caller's jobs, newest first, with status. **`GET /v1/jobs/:id`:**
    `Job` + `QueueStatus`; another user's job gives 404.
  - **`POST /v1/jobs/:id/cancel`** and **`PATCH /v1/jobs/:id`** (edit) map onto C8.
  - **`GET /v1/jobs/:id/file/:name`** (`video.mp4|poster.jpg|keyframes.jpg`) returns a 302 to a
    presigned R2 GET (5 min), owner only.
  - **`DELETE /v1/jobs/:id`** removes the result objects and marks the job deleted.
  - **`DELETE /v1/accounts/me`:**
    - cancels and refunds queued jobs;
    - deletes the R2 `uploads/<acct>/` and `jobs/<id>/` prefixes;
    - anonymises ledger rows (account id kept for integrity, email cleared);
    - is used by ModVision's delete-account (C31) and Valora's "Delete all data".
  - **`GET /v1/worlds`:** the site worlds (cached from the trusted worker's last `worlds` report;
    see C19).
  - **`GET /v1/estimate?tier&world&aspect`:** quote + ETA for a would-be job, without enqueueing.
- [ ] **Implement** `src/routes/user.ts` and `src/r2.ts` (SigV4 presign, with tests against AWS's
  published SigV4 test vectors). **Commit.**

### Task C14: Worker routes [parallel with C13, C15]

- [ ] **Failing tests:**
  - **`POST /v1/worker/claim`** `{identity:{gpuModel, blenderBuild, engineSha, pools}}`:
    - updates the `rc_workers` identity;
    - calls `rc_claim_next`;
    - returns 204 when there is nothing to do;
    - otherwise returns `WorkerClaim`, with presigned GETs for every input and presigned PUTs for
      the task's outputs, all 15 min;
    - render tasks get one PUT per remaining frame, `jobs/<id>/frames/NNNNNN.png`;
    - the input set per kind is: ingest ← upload; direct ← profile + upload; render ← script +
      profile + upload + bake keys; encode ← frames.
  - **`POST /v1/worker/tasks/:id/heartbeat`** gives `{cancel, leaseExpiresAt}`, or 409 `lease_lost`.
  - **`POST /v1/worker/tasks/:id/frames`** `{frames:[…]}` verifies each frame object exists in R2
    (HEAD) before `rc_report_frames`. A claimed-but-missing frame gives 422.
  - **`POST /v1/worker/tasks/:id/complete`:**
    - `{outputs, cost:{gpuS, bakeS, setupS, blocksSig, frames}, result?}`;
    - for `direct`, `result` carries `{frameCount, estSPerFrame, assetsHash, blocksSig, world}` →
      `rc_split_ranges`;
    - for `encode`, `result` carries `{creditLine, qc}`.
  - **`POST /v1/worker/tasks/:id/fail`** `{retryable, userMessage, detail}`.
  - **`POST /v1/worker/status`** `{accepting, quietHours?, state}`, which the switch calls.
  - **Worker presigned PUTs are scoped** to exactly the keys listed: a PUT to any other key has no
    URL to use.
- [ ] **Implement** `src/routes/worker.ts`. **Commit.**

### Task C15: Abuse filter, rate limits, reports [parallel with C13, C14]

- [ ] **Failing tests:**
  - **Prompt:** ≤ 1000 characters, and the Unicode categories Cc/Cf/Zl/Zp/Cs are rejected (the
    director §4.2a rule, ported and tested with the checker's own fixture strings).
  - **Markers:** ≤ 8, text ≤ 280, the same rule; ids match `^[a-z0-9_-]{1,32}$`.
  - **Blocklist:** `src/policy/blocklist.json`, versioned, whole-word, case-folded, homoglyph-folded.
    A hit gives 422 "This prompt can't be rendered." plus an `rc_reports` row with
    `reporter='system'`. The test uses placeholder words from a test-only list; the real list never
    enters test output.
  - **Rate limits:** per IP, 60 req/min overall and 5 enqueues/min, through the binding; a hit gives
    429 "Too many requests — try again in a minute."
  - **`POST /v1/reports`** `{jobId|modelSha256, reason}` inserts `rc_reports`; a user can report
    only a job they can see.
- [ ] **Implement, commit.**

### Task C16: Crons — reaper, outbox (email), cost rollup, retention

- [ ] **Failing tests** (`scheduled()` handler with a fake clock):
  - Every minute it calls `rc_reap_leases`.
  - **The outbox sends pending rows:**
    - without `RESEND_API_KEY` it logs and marks `skipped_no_provider`, never crashing;
    - with the key it POSTs to the Resend API (mocked fetch) using the templates `done`,
      `failed` and `turn_near` (plain sentences, a link to the job page, no file attached);
    - it retries up to 5 with backoff.
  - **`turn_near`** is queued when a job's `rc_queue_status` position = 1 and `eta_start_s < 300`,
    once per job.
  - **Retention:** frames older than 7 days, results older than 30 days, and unused uploads older
    than 30 days are deleted (R2 list + delete), plus job rows' `result_key` nulled. The bucket also
    gets an R2 lifecycle rule as a backstop (C34).
- [ ] **Implement, commit.**

---

## Chunk 3 (lane W): The worker — pull-only, on the owner PC first

**Shared rules for C17–C22:**

- Stdlib only at runtime (`urllib.request`, `json`, `hashlib`, `threading`, `subprocess`).
- The HTTP layer is injected, so tests use a `FakeApi` built from `core/contract/v1.json`
  examples.

### Task C17: Config, identity, ON/OFF switch, quiet hours, yield-to-owner

**Files:** `core/worker/{__init__,__main__,config,identity,switch}.py`, `core/tests/test_worker_identity.py`,
`core/tests/test_worker_switch.py`

- [ ] **Failing tests:**
  - **`identity()`** parses `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` (from a
    fixture string) into `"NVIDIA GeForce RTX 5080"`.
    - `blender_build` comes from `engine.blender_pin.parse_version(<blender --version>)` plus the
      build hash line.
    - `engine_sha` = `git rev-parse HEAD` of the worktree, plus a `+dirty` suffix when the tree has
      changes. A dirty engine refuses to claim render tasks, with a clear log line, because asset
      hashes would lie (H3).
  - **The switch state file** lives at `%LOCALAPPDATA%\Valora\worker\switch.json`:
    - `on()` sets `accepting=true`;
    - `off()` sets `draining`;
    - a second `off()` within 60 s sets `stop_now`;
    - the state persists across restarts.
  - **`in_quiet_hours(now, "23:00-07:00", tz)`:** true at 02:00 and false at 12:00, including the
    DST edges (fixture dates).
  - **`owner_using_gpu(smi_apps_csv, my_pids)`** is true when any other process holds > 1024 MB
    (eng). Blender child pids are excluded.
- [ ] **Implement, commit.**

### Task C18: Client and loop — claim, heartbeat thread, complete/fail, drain

**Files:** `core/worker/client.py`, `core/worker/loop.py`, `core/tests/test_worker_loop.py`

- [ ] **Failing tests** (FakeApi + fake runners):
  - **Idle backoff:** 204s back off 5 → 10 → 20 → 30 s (a fake sleep records the delays) and reset
    to 5 s after a claim.
  - **Heartbeats** go every `heartbeatS` while a runner works. `cancel:true` sets the runner's cancel
    event. The loop then stops the Blender subprocess (fake), reports nothing more, and claims
    again.
  - **`lease_lost`** on a heartbeat has the same effect as a cancel, and does not call complete.
  - **Runner exceptions:**
    - `EngineInputError` → `fail(retryable=false, userMessage=<its sentence>)`;
    - any other exception → `fail(retryable=true, userMessage="The render machine hit a problem.
      Retrying.")`;
    - the traceback goes only to `detail`, capped at 4 KB.
  - **Draining:**
    - finishes the current task, then posts `status accepting=false` and exits 0;
    - `stop_now` cancels the current task, posts `fail(retryable=true)` so the range returns
      immediately with its frames kept, and exits.
  - **Quiet hours or owner-using-GPU** skip the claim (no HTTP call) and post status once per
    change.
  - **No listening socket:** `psutil`-free check.
    - Run the loop for 3 iterations in a thread, then read `netstat -ano -p TCP` (Windows) or
      `/proc/net/tcp` (else).
    - Assert no LISTEN row belongs to this pid.
    - Marker `integration`; runs in the chunk gate.
  - **Network errors** retry with jitter and never crash the loop. After 10 minutes offline the loop
    logs once; the lease is simply lost server-side.
- [ ] **Implement, commit.**

### Task C19: Task runners on the engine seams [parallel with C20, C21]

**Files:** `core/worker/runners.py`, `core/tests/test_worker_runners.py`

- [ ] **Failing tests** use monkeypatched `ingest`, `direct_site` and `compile_scene`, the same
  seams `engine/site_job.py` tests use:
  - **`ingest`** downloads the upload, verifies sha256 (a mismatch gives non-retryable "The upload
    was damaged in transit. Upload it again."), runs `ingest`, and puts `profile.json`.
  - **`direct`** calls `direct_site(prompt, profile, world=, aspect=, seed=, duration=, provider=)`
    with the **site catalog** (H4). It:
    - asserts `site_deliverable(script) == []` before returning;
    - puts `script.json` and `replay.json`;
    - returns `{frameCount, estSPerFrame(from the script's blocks via /v1 estimate echo),
      assetsHash, blocksSig, world}`.
    - `DirectorInputError` gives a non-retryable fail with its message.
    - Markers pass through as `--markers`-equivalent input.
    - **Keyframes storyboard** (spec §15 seed): after direct, render `tier="keyframes",
      frames="key"` (fake in tests; ~3 frames, eng) and put `keyframes.jpg` (a contact strip). A
      failure here is logged, never fatal.
  - **`render`** calls `compile_scene(script, profile, model, out, tier=job tier,
    frames=[f for f in range(start, end+1) if f not in frames_done])`. After each frame file
    appears (a poll of `render/beauty/NNNN.png`, as `site_job` documents), it:
    - PUTs the frame;
    - calls `/frames` in batches of ≤ 5 (or every 20 s);
    - on cancel, kills Blender and returns.
  - **`encode`** downloads frames, then:
    - runs **frame QC** (director §4.8) as **report-only** (`qc` in the result, never blocks — not
      yet calibrated);
    - runs ffmpeg at the job fps with colour tags;
    - applies the watermark when the job's preset marks it (port `ModVision/tools/render-studio/watermark.py`,
      server-authoritative);
    - writes the credit line into MP4 metadata (`-metadata comment=…`);
    - adds a 1.5 s end card when `requires_visible_credit`;
    - makes the poster from the hook frame (t = 0.5 s, as `director.py` does);
    - re-checks the licence via the job's `creditLine`/`licenceOk` fields (belt and braces);
    - puts `video.mp4` and `poster.jpg`.
  - **Worlds report:** a trusted worker posts `engine.site_job.worlds()` to `/v1/worker/status`
    every 10 minutes, so `GET /v1/worlds` never needs a listener on the PC.
- [ ] **Implement, commit.**

### Task C20: Sandbox [parallel with C19, C21]

**Files:** `core/worker/sandbox.py`, `core/tests/test_worker_sandbox.py`

- [ ] **Failing tests:**
  - **`task_dir()`** makes a fresh dir under `%LOCALAPPDATA%\Valora\worker\tasks\<taskId>` and
    deletes it on exit, even on exception.
  - **`scrubbed_env(kind)`:**
    - drops `VALORA_WORKER_TOKEN`, every `*_KEY`/`*_SECRET`/`*_TOKEN`, and `SUPABASE_*`;
    - keeps `ANTHROPIC_API_KEY` **only** for `kind == "direct"` on a trusted worker.
  - **The Blender argv** always contains `--factory-startup` and `--disable-autoexec`. Assert on
    `engine.blender_cli` usage, and add them there only via a merge from `renderer/director` if
    missing. Never edit `engine/` from this branch; if missing, file it as a registry patch for
    the engine lane.
  - **Download caps:** the upload is ≤ 200 MB, and a stream over the declared `bytes` is aborted.
  - **Disk guard:** free space < 20 GB (eng) refuses to claim render tasks and posts the status
    `low_disk`.
- [ ] **Implement, commit.**

### Task C21: Cost logging [parallel with C19, C20]

- [ ] **Failing tests:**
  - `gpu_s` is the wall time inside `compile_scene` minus `setup_s`. `setup_s` is the time to the
    first frame file.
  - `bake_s` comes from the phase-6 `compile.json` `bakeSeconds` when present.
  - `usd = (gpu_s + setup_s) × hourly_cost_usd / 3600`.
  - `blocksSig` = the sorted `_refs(script)` from `engine/director/site.py` (import, don't copy).
  - Every `complete` carries these fields, and a missing field is a contract-test failure.
- [ ] **Implement, commit.**

### Task C22: Owner-PC install — enrol, DPAPI token, ON/OFF shortcuts, logon task

- [ ] **Failing tests:**
  - **`enroll(code)`:**
    - POSTs `/v1/worker/enroll` (a one-time code from the admin view, 15 min; the route is added to
      lane A in this task);
    - stores the returned secret with DPAPI (`CryptProtectData` via `ctypes`; tests use a fake
      protector);
    - never prints it.
  - **`install()`** writes two `.lnk` shortcuts to the Desktop, "Render worker ON" and "Render
    worker OFF", running `py -m core.worker on|off`. Tests go through a fake shell writer. It also
    registers a Task Scheduler task **at logon, current user, not elevated**:

    ```
    schtasks /Create /SC ONLOGON /TN "Valora Render Worker" /TR "...\py.exe -m core.worker run" /RL LIMITED
    ```

    Assert on the argv, and never run it in tests.
  - **`uninstall()`** removes both, and deletes the DPAPI blob.
  - **Logs** go to `%LOCALAPPDATA%\Valora\worker\worker.log` (rotating, 5 × 5 MB), with no secrets:
    a test greps the log for the fake token.
- [ ] **Implement, commit.** **Lane-W chunk gate:** the full core suite, the integration marker and
  the engine frozen baseline 90/90.

---

## Chunk 4: Front-ends

### Lane V (Valora, worktree `rendering-valora`, `apps/web`)

#### Task C23: Cloud services behind the existing interfaces; deliberate tripwire rewrite

**Files:**
- Create: `lib/services/cloud/{auth,credits,render,api}.ts` + tests.
- Modify: `lib/services/index.ts`, `lib/schema/project.ts`, `lib/services/local/services.test.ts`,
  the e2e `not_connected` spec (find it with `rg -n "not_connected" apps/web/e2e`).

- [ ] **Failing tests:**
  - `CloudRenderService.requestPreview(projectId, versionId)` builds an `EnqueueRequest` from the
    project's current version, uploads the model if needed (`POST /v1/uploads` → PUT), and returns
    a `RenderJob` with `status "QUEUED"`, a `position` and an `etaS`.
  - `requestFinal(..., "cloud")` passes `parentJobId` when the version has a finished preview (spec
    §15 "preview-first finals"). `target "local"` gives the fail `not_available`, "Local rendering
    isn't available." There is no desktop agent.
  - `subscribe` polls every 10 s while `document.visibilityState === "visible"` and every 60 s when
    hidden. It stops on a terminal status, and its unsubscribe stops the timers (fake timers).
  - `CloudCreditService.post` does not exist on the cloud class. `CreditService` is split into a
    read interface for the client, and the pricing UI's `useGrant` is removed or dev-only.
  - `SupabaseAuthService`:
    - `signIn(email)` sends a magic link;
    - `signUp` requires an invite code (C25);
    - `signInWith("google")` returns `fail("not_available", ...)` until the owner's OAuth client
      exists;
    - `continueAsGuest` is removed (beta accounts only).
  - The schema widening validates the contract's `Job` examples: `RenderJobSchema.parse(example)`.
  - **Tripwire rewrite:** `services.test.ts:79`'s `not_connected` assertion becomes "cloud render
    service is wired and needs sign-in". The e2e spec asserts the queue line renders against a
    mocked API. **Do not delete these tests; rewrite them.**
- [ ] **Implement.**
  - `index.ts` picks the cloud services when `NEXT_PUBLIC_RENDER_API` is set, else the local ones
    (dev and tests).
  - Read the Next docs in `node_modules/next/dist/docs/` for env var exposure first.
- [ ] Run `npm test` and `npm run typecheck`. **Commit.**

#### Task C24: Queue UI — "You're #3 · ~12 min", cancel, notify [parallel with C25, C26]

**Files:** `components/studio/QueueLine.tsx` (+ test), `JobProgress.tsx`, `RenderPanel.tsx`,
`lib/notify.ts` (+ test)

- [ ] **Failing tests:**
  - **`queueLine(job)` copy:**
    - `{position:3, etaS:700}` → "You're #3 · ~12 min";
    - a band wider than ±30% → "You're #3 · 12–18 min";
    - `position 1, etaS<60` → "You're next";
    - `waitReason no_worker_online` → "Waiting for a GPU to come online";
    - `quiet_hours_until` → "Starts at 07:00" (user locale time);
    - `lane_overnight` → "Ready by morning";
    - `queue_paused` → "Paused for maintenance — your place is kept";
    - once `RENDERING`, it shows the frame progress already in `JobProgress`.
  - **Cancel:**
    - shows the refund sentence from the server's quote ("You'll get 30 credits back.", or "You'll
      get 27 credits back — 3 were used." mid-render);
    - asks for confirmation once;
    - the button is the single secondary action;
    - the white primary fill is never on Cancel (monochrome rule).
  - **Notify:**
    - `lib/notify.ts` asks `Notification.requestPermission()` only on the first Render press;
    - it fires `new Notification("Your render is ready", {body: title})` on the transition to
      `COMPLETE` when the tab is hidden, and never twice per job (localStorage try/catch);
    - the Settings toggle for email maps to `accounts.notify_email`.
  - **Keyframes:** when `keyframes.jpg` exists, the waiting state shows it as the hero image ("Your
    shots"), else the model thumbnail.
  - **Reduced motion:** no pulsing on the queue line (`useReducedMotion`).
- [ ] **Implement** in the existing Studio visual language (`components/ui`, `DUR`/`EASE` tokens).
  **Commit.**

#### Task C25: Invite-only sign-up [parallel]

- [ ] **Failing tests:**
  - `/invite?code=…` validates the code through `POST /v1/invites/redeem` (added to lane A:
    `rc_invites` `code_hash` + `used < max_uses`, not expired), then signs up with a magic link.
  - The first sign-in posts the `beta_grant` ledger row once (`idem_key = 'beta:'||account`).
  - A reused or exhausted code gets "This invite has been used up. Ask for a new one."
  - Cloudflare Access still wraps the site (no change to `wrangler.jsonc` routes).
- [ ] **Implement.** The lane A route and the web page. **Commit.**

#### Task C26: Admin queue view [parallel]

**Files:** `app/(app)/admin/queue/page.tsx`, `components/admin/{QueueTable,WorkersTable,SpendCard,CostTable,ReportsTable}.tsx`,
and lane A routes `GET /v1/admin/{queue,workers,spend,costs,reports}` plus
`POST /v1/admin/{pause,drain,cancel,grant,revoke-worker,enroll-code,showcase}` (admin-only, every
action → `rc_events`).

- [ ] **Failing tests:**
  - A non-admin gets 403 and the page shows "Admins only."
  - **Queue table:** rows in `rc_runnable_order` order, with user (email masked `d***@gmail.com`),
    lane, position, ETA, state, attempts and age.
  - **Workers:** name, accepting, quiet hours, pin triple, current task and frames, last seen, plus
    "Drain" and "Revoke".
  - **Spend today:** Σ usd vs `daily_spend_cap_usd` (P1: owner-PC electricity only).
  - **Cost per clip:** the median GPU-min and usd per `(tier, world)` and per `blocksSig`, from
    `rc_cost_samples`, with the sample count shown next to every median. The population is printed
    next to every number (a standing rule).
  - **Actions** call their routes. "Promote to showcase" requires the job be `COMPLETE` and asks for
    a short title.
- [ ] **Implement.** Monochrome, with a dense table layout; the admin is a tool, not a creator
  surface. **Commit.**

### Lane V2 (Valora §2b, worktree `rendering-valora`; independent of the core, can start day 1)

#### Task C27: Viewer stops pretending; three display modes [parallel with C28]

**Files:** `components/viewer/{Viewer,SceneEnvironment,Sky,RainLayer,palette,Model}.tsx|ts` + tests,
`components/studio/ControlsPanel.tsx`

- [ ] **Failing tests:**
  - The Viewer tree contains no `RainLayer`, and no weather/fog/fake-grade node for any
    `ScenePlan` environment. `environmentLook.ts` keeps only a neutral backdrop.
  - **`displayMode` ∈ `plain|zones|final`, default `plain`:**
    - `plain` gives every mesh one matte neutral material (monochrome token);
    - `zones` gives one flat colour per material class, from an 8-tone monochrome-safe ramp. The
      class ids are the ones ingest writes (`SubjectProfile.materials[].class`); mirror the
      classifier the web already has in `lib/scene/classify.ts`, or read it from the analysis;
    - `final` gives the file's own materials.
  - A segmented control with three picture chips (Plain / Zones / Final) sits in the viewer's top
    bar, and it is the only new control.
  - `ThumbnailCapture` always captures in `final`.
- [ ] **Implement, commit.**

#### Task C28: Point-and-describe markers [parallel with C27]

**Files:** `components/viewer/Markers.tsx`, `lib/scene/markers.ts` (+ tests),
`components/studio/Composer.tsx`

- [ ] **Failing tests:**
  - **`toGltfSpace(pointViewer, normalisation)`** inverts `FitCamera`/`sceneScale`'s recentre,
    rescale and rotate. Round trip `fromGltf(toGltf(p)) ≈ p` (1e-6). A known fixture: a unit cube
    offset by (10, 0, 0), scaled ×0.01 by the viewer, gives the anchor back in file units.
  - Clicking the model (raycast) adds pin N (max 8; the 9th click gets "Up to 8 notes per render.").
    Each pin opens a small note field (1–280 characters, with the same Unicode rule as the API,
    shared from `lib/scene/markers.ts`) and an optional "at 3 s" moment (≤ duration).
  - The `part` field is the zone id under the cursor when `displayMode === "zones"`; otherwise it is
    omitted.
  - The markers serialize into `EnqueueRequest.markers` exactly per director §4.2a, with `space:
    "gltf"`. The contract example validates.
  - The pins render as numbered monochrome dots with an outline for dark/light backgrounds; the
    overlay budget is one element per pin.
- [ ] **Implement, commit.**

#### Task C29: Showcase gallery from owner-graded renders [after C26's "promote"; gallery half gated]

- [ ] **Failing tests:**
  - `showcase.ts` reads `showcase.json` (served from R2 via `render-api` `GET /v1/showcase`,
    public, cached 5 min) and falls back to the current `manifest.ts` tiles when it is empty.
  - **Variety rule:** `arrange(tiles)` never puts two adjacent tiles of the same `world` or the same
    `subjectClass`. With an impossible input (all the same) it keeps the order and logs once.
  - A tile needs `ownerGrade === "KEEP"` and a poster + mp4; others are dropped.
- [ ] **Implement.** `Gallery.tsx` reads through `showcase.ts`. **The owner grades each candidate**
  (KEEP / CHANGE / STOP), one sheet per clip, before promotion. Until then the gallery stays on the
  current manifest. **Commit.**

### Lane M (ModVision, `C:\Users\deand\Projects\ModVision`)

#### Task C30: `CoreRenderProvider`; the Render Studio queue line; retire the loopback queue

**Files:**
- Modify: `js/render-studio/provider.js`, `provider.test.js`, `ui.js`, `config.js`, `config.test.js`.
- Delete (after the C32 cutover passes): `tools/render-studio/server.py` job routes, `jobs.py`
  `JobStore` and the queue, the `director.py` subprocess bridge, and their tests. Keep
  `render_cars.py` until C31 moves its gate.

- [ ] **Failing tests** (`node --test`):
  - `CoreRenderProvider` keeps the **same method set** as `LocalRenderProvider` (`health`, `scenes`,
    `estimate`, `submit`, `list`, `get`, `cancel`, `remove`, `retry`, `fileUrl`, `subscribe`).
    Every request carries `Authorization: Bearer <ModVision Supabase token>` and
    `X-Render-Tenant: modvision`, to `RENDER_API` from `config.js`.
  - `submit(job, snapshot)` computes the snapshot sha256 (SubtleCrypto), does
    `POST /v1/uploads` → PUT (skipped when `exists`), then `POST /v1/jobs` with `modelKey = job.car`
    and a fresh `idemKey`. There is no 128 MB JSON body any more.
  - `retry(id)` = enqueue a copy with a new idemKey (the server has no retry route).
  - `fileUrl(id, name)` follows the API's 302 to the presigned URL (no blob proxying needed, since
    R2 presigned GETs work in `<video src>`). The blob fallback stays only for tests.
  - The constructor still throws off-loopback (the page stays dev-only; spec §8.3).
  - `ui.js` shows the queue line with the same copy function as Valora. Port `queueLine()` as a tiny
    shared pure module duplicated with a parity test: both repos test the same fixture table in
    `core/contract/v1.json` `x-queue-copy`. It also shows Cancel with the refund sentence, and a
    `QUALITY.final.hint` from `/v1/estimate` ("~8 h · overnight").
  - The "Render server offline" message becomes "Can't reach the render queue — your renders are
    safe."
- [ ] **Implement.** Then run ModVision's gates for UI changes: `npm run smoke`, `npm run
  check:escape`, `npm run check:inline-style`, `npm run check:primary-fill`, `npm run
  check:selected-fill` and `npm run check:motion`. **Commit** (paths only, after auditing
  `git diff --cached --name-only` against the shared index).

#### Task C31: Licence sync, delete-account hook, SUPERSEDED header

- [ ] **Failing tests:**
  - **`scripts/sync-render-licences.mjs --dry`** reads the shipping fleet (the existing
    `scripts/lib/shipping-cars.mjs`; no second parser of `LICENSED_CAR_IDS`) and a new committed
    `data/render-licences.json`. That file maps `carId → {allowsVideoExport, allowsDownload,
    creditLine, requiresVisibleCredit, evidenceRef}`, filled from `docs/licensing/*` by Claude with
    each row's evidence path.
    - It prints the rows it would upsert, and **lists every shipping car with no reviewed row as
      DENIED (unknown)**.
    - `--apply` POSTs to `POST /v1/admin/licences` (admin token).
    - `render-denied-cars.json` is folded in (denied stays denied) and then deleted.
  - **`supabase/functions/delete-account`** also calls `DELETE /v1/accounts/me` with the user's
    token. A render-api failure does not block ModVision's own deletion; it logs and queues a retry
    row. Test it with the function's existing harness.
  - The header of `docs/security/2026-09-28-render-videos-bucket.sql` becomes "SUPERSEDED
    2026-09-28 by the render core (rendering repo spec 2026-09-28-render-core-and-queue-design.md);
    never run."
- [ ] **Implement, commit.** **The owner reviews `data/render-licences.json` before `--apply`**
  (owner-only item 8).

---

## Chunk 5: Prove it, secure it, ship the private beta

### Task C32: End to end (owner-OK preview renders only)

- [ ] **Staging.**
  - Apply migrations to the render-core project: `py -m core.db.migrate --url $RC_DB_URL`, where
    the URL is the owner's connection string.
  - `wrangler deploy` `render-api` to a `*.workers.dev` preview **or** the real custom domain
    (C34).
  - Enrol the owner PC (`py -m core.worker enroll <code>`), then `on`.
- [ ] **Scripted checks** (`core/tests/e2e_live.py`, marker `live`; each prints its evidence):
  1. **Valora preview:** the product-render subject (`assets-in/models/` camera), prompt `""`.
     Keyframes appear, the preview renders, and the email plus browser notification arrive. One
     `capture`, `available` drops by 3.
  2. **ModVision preview** of the default car (GT3 RS), in the rain world if graded: the licence row
     allows it, and the credit line is in MP4 metadata (`ffprobe`).
  3. **Crash-resume:** mid-range, kill the worker process (`taskkill /PID`), restart it after the
     lease expires, and confirm it resumes from `frames_done`. One capture and `attempts == 2` on
     that task.
  4. **Fairness live:** 3 test accounts, where A enqueues 3 previews and B and C 1 each. The claim
     order recorded in `rc_events` is A1 B1 C1 A2 A3, and each user's "#N" matched it at enqueue
     time.
  5. **Cancel refund:** cancel a queued job, and credits return within one poll.
  6. **Switch:** OFF drains within one range, and the ETA shows "Waiting for a GPU to come online".
     Quiet hours in the next 2 minutes stop new claims.
  7. **ETA sanity:** the predicted vs. actual start and done go into the register (population:
     these N jobs, today).
- [ ] **Budget:** preview tier only. Stop after these checks; no final is rendered without the
  owner's go.
- [ ] **Cutover:** ModVision's Render Studio runs against the core. Only then is the C30 deletion of
  the loopback queue committed.

### Task C33: Security review

- [ ] Run the `differential-review` and `insecure-defaults` skills on the `render-core` branch diff
  and on the ModVision and Valora diffs.
- [ ] **Checks:**
  - no service key outside `render-api` secrets;
  - RLS on every `rc_*` table (a SQL query lists any table with `relrowsecurity = false`, and the
    list must be empty);
  - every `security definer` function has a pinned `search_path`;
  - presigned URL TTLs ≤ 15 min;
  - CORS allow-list exact;
  - no stack traces in error bodies;
  - worker log has no secrets;
  - **no listening socket** on the owner PC while the worker runs (C18 test, run live);
  - secret scan of all three diffs.
- [ ] `fp-check` each finding. Fix the true positives and re-run.

### Task C34: Deploy, invite, register, hand-off

- [ ] **`render-api`:** add the custom domain `render-api.valora3d.com`. Set a Cloudflare Access
  **bypass** policy for that hostname only; every route authenticates itself. Add the R2 lifecycle
  rules (frames 7 d, results 30 d).
- [ ] **Valora:** deploy `site/valora3d-preview` with `NEXT_PUBLIC_RENDER_API` set. **Access stays
  on.**
- [ ] **ModVision:** no production deploy is needed; Render Studio is dev-only. If any shipped file
  changed, follow `mv-deploy` and its `updates.html` rule.
- [ ] **Invites:** create codes from the admin view for the owner's list (owner-only item 6).
- [ ] **Calibration register** (append to this plan). Every (eng) number, with its population and
  date:
  - lease/heartbeat;
  - `range_target_s`;
  - `short_lane_max_s`;
  - `age_promote_s`;
  - weights;
  - caps;
  - the overnight discount;
  - the yield VRAM threshold;
  - the disk guard;
  - rate limits;
  - the ETA error from C32;
  - the owner-PC $/h.
- [ ] **Hand-off:** `.handoffs/YYYY-MM-DD-HHMM-render-core-p1-private-beta-done.md` with
  `track: render-core` in the frontmatter and filename, plus the latest-handoff row.

---

## P2 outline: rented GPU farm + autoscale

1. **Measure before buying.**
   - Rent 1 hour each of 2 candidate SKUs on the owner-chosen provider (director §12 Q1).
   - Run the product and rain preview recipes, and log s/frame and $/frame into `rc_cost_samples`.
   - The owner picks the SKU; one SKU per pool (H3).
2. **Container image.**
   - Blender 5.0.1 (`engine/blender_pin.py`), the engine at a pinned sha, the worker and ffmpeg.
   - Its digest is recorded as `blender_build`/`engine_sha` identity.
   - The container is disposable per task; `--exit-when-idle 300`.
3. **Same-pin fan-out** of a final's ranges across pods. A seam test renders ranges on 2 pods and
   runs the QC flicker check at the boundary.
4. **CPU bake class** (PHASING 7b). A `bake` task runs on CPU pods or the owner PC. Caches ship by
   key to `bake/<key>/` in R2, and render workers never simulate (7a). Cost splits into bake-s and
   GPU-s (7c).
5. **Autoscaler cron.**
   - `need = ceil(Σ ready gpu est / wait_target_s) − (online + booting)`.
   - It is bounded by `max_pods` and **`daily_spend_cap_usd`**, and ignores the overnight lane.
   - It emails the admin once at the cap.
   - Provider API calls are behind an interface with a fake for tests.
6. **Trusted CPU box** for ingest/direct, so the owner PC can be OFF without stalling the queue.
   It is a small owned VM that also only pulls.
7. **Web Push** (VAPID, service worker) for closed tabs. **Realtime** job updates to replace
   polling.
8. **Poster NSFW check** before a final's result is released. **Cloud projects** (Valora
   `projectRepository` → Postgres + R2).
9. **Public status line** ("GPUs online · typical wait ~N min"). Goodwill credits for ETA misses
   (owner decision, off by default).
10. **Showcase gallery** finished if C29's graded half did not land in P1.

## P3 outline: payments + public launch (gated on the owner lifting the marketing hold)

1. **Stripe Checkout** for `CREDIT_PACKS` and Stripe subscriptions for Creator/Pro.
   - The `POST /v1/stripe/webhook` signature is verified, and ledger rows use `idem_key =
     stripe:<event_id>`.
   - Plan changes update `plan`/`weight`.
   - Chargebacks post `adjust` rows and suspend.
   - All of this needs the owner's account and keys.
2. **Re-price** credits from the cost-per-clip report (director §12 Q2) before any sale.
3. **Legal pages:** ToS, privacy, refund, acceptable use, and the DMCA agent. **Supabase Pro +
   PITR.**
4. **Replace Cloudflare Access** on `valora3d.com` with public pages plus Supabase sign-in, then
   lift the invite gate.
5. **Load test:** 200 synthetic users against a staging project. Check that the claim p95 and the
   `rc_queue_status` p95 stay under 100 ms, and add indexes as measured.
6. **Launch comms** only after the owner lifts the hold. The ModVision `updates.html` entry per the
   deploy rule.

---

## What grew from the seed

The owner's line was "a queue for the GPUs if people are waiting". These items are in P1 without
being asked for:

- the keyframes storyboard while waiting (C19/C24);
- preview-first finals (C23);
- "your turn is near" emails (C16);
- honest wait reasons instead of fake numbers (C9/C24);
- admission control that offers overnight or preview (C4);
- idempotent submit (C4/C13);
- one-capture crash-safe money (C8);
- stickiness to avoid scene reloads (C6);
- yield-to-owner on GPU memory (C17);
- a dirty-engine refusal so asset hashes never lie (C17);
- per-block cost tables feeding pricing (C21/C26);
- ETA self-calibration (C32/C34);
- the showcase promotion flow with a variety rule (C26/C29);
- licence "unknown means no" (C31).

P2 carries the public status line and goodwill credits for ETA misses.

## Calibration register

Filled in C34. Every (eng) number listed in spec §5 `settings`, §6.8, §7.2 and §10, and in this
plan, gets its population and date.

| Number(s) | Where | Calibrated through |
|---|---|---|
| lease 120 s, heartbeat 30 s, max attempts 3 | `rc_settings` | C32 crash test; P1 logs |
| range target 10 min; short lane ≤ 20 min; age promote 45 min | `rc_settings` | C32 + first beta week's `rc_events` |
| weights beta/free 1, creator 2, pro 4 | `rc_accounts` | Owner decision (P3 pricing) |
| caps: 1 final + 2 previews active, 10/day, 3 finals/week, 12 h queued | `rc_settings`/`rc_prices` | Beta week 1 |
| overnight discount 40% | `rc_prices` | Owner decision |
| yield > 1 GB VRAM; disk guard 20 GB | worker config | C32 on the owner PC |
| rate limits 60/min, 5 enqueues/min | render-api | Beta week 1 |
| s/frame defaults 7 (preview) / 95 (final), setup 60 s | `rc_estimate` | Replaced by `rc_cost_samples` medians |
| owner-PC $/h 0.06 | `rc_workers.hourly_cost_usd` | Owner's electricity rate |
