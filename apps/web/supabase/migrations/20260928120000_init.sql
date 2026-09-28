-- Valora3D backend foundation (Lane A, 2026-09-28).
--
-- Tables: profiles, projects, uploads, scene_versions, render_jobs, credit_ledger (+ credit_balances view).
-- Rules (docs/launch-plan.md, "Security rules"):
--   * RLS is on for every table. Users read only their own rows.
--   * credit_ledger, render_jobs and uploads are written only by the service role (API routes).
--   * No SECURITY DEFINER anywhere. Money-moving functions are SECURITY INVOKER, EXECUTE is granted
--     to service_role only, and they run inside the API route's single call (one transaction).
--   * The new-user trigger runs as supabase_auth_admin, which is granted exactly the two INSERTs it
--     needs (profile + signup grant) through explicit policies.

-- ---------------------------------------------------------------------------------------------
-- Constants
-- ---------------------------------------------------------------------------------------------

-- Credits granted once to every new account (the Free plan). Mirrors FREE_PLAN_CREDITS in
-- apps/web/lib/pricing.ts; lib/pricing.test.ts fails if the two drift.
create or replace function public.free_plan_credits() returns integer
language sql immutable parallel safe
set search_path = ''
as $$ select 50 $$;

-- Largest accepted upload, in bytes (200 MB). Mirrors MAX_UPLOAD_BYTES in lib/pricing.ts.
create or replace function public.max_upload_bytes() returns bigint
language sql immutable parallel safe
set search_path = ''
as $$ select 209715200::bigint $$;

-- ---------------------------------------------------------------------------------------------
-- Types
-- ---------------------------------------------------------------------------------------------

create type public.plan_tier as enum ('free', 'creator', 'pro');
create type public.upload_status as enum ('pending', 'ready', 'rejected');
create type public.render_job_status as enum ('queued', 'running', 'succeeded', 'failed', 'cancelled');
create type public.render_job_kind as enum ('preview', 'final');

-- ---------------------------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------------------------

create table public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  email       text not null,
  name        text not null default '' check (char_length(name) <= 120),
  avatar_seed text not null default gen_random_uuid()::text,
  plan        public.plan_tier not null default 'free',
  prefs       jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table public.projects (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name                text not null check (char_length(name) between 1 and 200),
  asset_id            uuid,
  analysis            jsonb,
  selected_version_id uuid,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
create index projects_user_updated_idx on public.projects (user_id, updated_at desc);

-- A model file in R2 (source 'upload') or a built-in sample (source 'sample', no r2 key).
-- Doubles as the studio's "asset".
create table public.uploads (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  project_id    uuid references public.projects (id) on delete cascade,
  source        text not null default 'upload' check (source in ('upload', 'sample')),
  file_name     text not null check (char_length(file_name) between 1 and 255),
  format        text not null default 'glb' check (format in ('glb', 'gltf', 'fbx', 'obj')),
  r2_key        text unique,
  sample_url    text,
  size_bytes    bigint not null check (size_bytes >= 0 and size_bytes <= public.max_upload_bytes()),
  sha256        text check (sha256 is null or sha256 ~ '^[0-9a-f]{64}$'),
  status        public.upload_status not null default 'pending',
  reject_reason text,
  created_at    timestamptz not null default now(),
  completed_at  timestamptz,
  -- An upload always lives under its owner's prefix; a sample never has a key.
  constraint uploads_key_prefix check (
    (source = 'upload' and r2_key is not null and r2_key like 'u/' || user_id::text || '/%')
    or (source = 'sample' and r2_key is null)
  ),
  -- Only single-file .glb is accepted as a real upload.
  constraint uploads_glb_only check (source = 'sample' or format = 'glb')
);
create index uploads_user_idx on public.uploads (user_id, created_at desc);
create index uploads_project_idx on public.uploads (project_id);

create table public.scene_versions (
  id         uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  index      integer not null check (index >= 0),
  prompt     text not null default '',
  parent_id  uuid references public.scene_versions (id) on delete set null,
  plan       jsonb not null,
  created_at timestamptz not null default now(),
  unique (project_id, index)
);

create table public.render_jobs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users (id) on delete cascade,
  project_id      uuid not null references public.projects (id) on delete cascade,
  version_id      uuid references public.scene_versions (id) on delete set null,
  upload_id       uuid references public.uploads (id) on delete set null,
  kind            public.render_job_kind not null default 'final',
  status          public.render_job_status not null default 'queued',
  params          jsonb not null default '{}'::jsonb,
  runpod_id       text unique,
  output_keys     text[] not null default '{}',
  cost_credits    integer not null check (cost_credits >= 0),
  error           text,
  -- Client idempotency key: a retried "Render" click returns the same job, charged once.
  idempotency_key text,
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  finished_at     timestamptz,
  updated_at      timestamptz not null default now(),
  unique (user_id, idempotency_key)
);
create index render_jobs_user_idx on public.render_jobs (user_id, created_at desc);

-- Append-only. amount is signed: grants positive, spends negative.
-- ref is globally unique so every grant/debit/refund is idempotent
-- (e.g. 'signup:<uid>', 'render:<job>', 'refund:<job>', 'paddle:<event>').
create table public.credit_ledger (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users (id) on delete cascade,
  amount     integer not null check (amount <> 0),
  reason     text not null check (reason in (
               'signup_grant', 'plan_grant', 'pack_purchase',
               'scene_generation', 'prompt_edit', 'preview_render', 'render_final',
               'render_refund', 'admin_adjustment')),
  ref        text not null unique,
  project_id uuid references public.projects (id) on delete set null,
  job_id     uuid references public.render_jobs (id) on delete set null,
  created_at timestamptz not null default now()
);
create index credit_ledger_user_idx on public.credit_ledger (user_id, created_at desc);

-- The ledger is never edited: corrections are new rows. Deletes happen only by cascade when
-- an account is deleted (and by the service role). Setting a FK column to null on a parent delete
-- is the one allowed update.
create or replace function public.credit_ledger_block_update() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.user_id is distinct from old.user_id
     or new.amount is distinct from old.amount
     or new.reason is distinct from old.reason
     or new.ref is distinct from old.ref
     or new.created_at is distinct from old.created_at then
    raise exception 'credit_ledger is append-only' using errcode = '42501';
  end if;
  return new;
end $$;

create trigger credit_ledger_append_only
  before update on public.credit_ledger
  for each row execute function public.credit_ledger_block_update();

-- Balance per user. security_invoker makes the view obey the caller's RLS on credit_ledger.
create view public.credit_balances
with (security_invoker = true) as
  select user_id, coalesce(sum(amount), 0)::integer as balance
  from public.credit_ledger
  group by user_id;

-- updated_at bookkeeping.
create or replace function public.touch_updated_at() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end $$;

create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();
create trigger projects_touch before update on public.projects
  for each row execute function public.touch_updated_at();
create trigger render_jobs_touch before update on public.render_jobs
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------------------------
-- Privileges + RLS
-- ---------------------------------------------------------------------------------------------

alter table public.profiles       enable row level security;
alter table public.projects       enable row level security;
alter table public.uploads        enable row level security;
alter table public.scene_versions enable row level security;
alter table public.render_jobs    enable row level security;
alter table public.credit_ledger  enable row level security;

-- Start from nothing, then grant exactly what each role needs.
revoke all on public.profiles, public.projects, public.uploads, public.scene_versions,
              public.render_jobs, public.credit_ledger, public.credit_balances
  from anon, authenticated;

grant select on public.profiles, public.projects, public.uploads, public.scene_versions,
                public.render_jobs, public.credit_ledger, public.credit_balances
  to authenticated;
-- Profiles: a user may change their name and prefs only (plan is set by billing, server-side).
grant update (name, prefs) on public.profiles to authenticated;
-- Projects and versions are plain user content.
grant insert, update, delete on public.projects to authenticated;
grant insert on public.scene_versions to authenticated;
-- uploads, render_jobs, credit_ledger: no user writes at all (service role only).

grant all on public.profiles, public.projects, public.uploads, public.scene_versions,
             public.render_jobs, public.credit_ledger, public.credit_balances
  to service_role;

-- profiles
create policy profiles_select_own on public.profiles
  for select to authenticated using (id = (select auth.uid()));
create policy profiles_update_own on public.profiles
  for update to authenticated using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- projects
create policy projects_select_own on public.projects
  for select to authenticated using (user_id = (select auth.uid()));
create policy projects_insert_own on public.projects
  for insert to authenticated with check (user_id = (select auth.uid()));
create policy projects_update_own on public.projects
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy projects_delete_own on public.projects
  for delete to authenticated using (user_id = (select auth.uid()));

-- uploads (read-only for users)
create policy uploads_select_own on public.uploads
  for select to authenticated using (user_id = (select auth.uid()));

-- scene_versions: insert only into a project the user owns.
create policy versions_select_own on public.scene_versions
  for select to authenticated using (user_id = (select auth.uid()));
create policy versions_insert_own on public.scene_versions
  for insert to authenticated with check (
    user_id = (select auth.uid())
    and exists (select 1 from public.projects p where p.id = project_id and p.user_id = (select auth.uid()))
  );

-- render_jobs + credit_ledger (read-only for users)
create policy render_jobs_select_own on public.render_jobs
  for select to authenticated using (user_id = (select auth.uid()));
create policy credit_ledger_select_own on public.credit_ledger
  for select to authenticated using (user_id = (select auth.uid()));

-- ---------------------------------------------------------------------------------------------
-- New user: profile + one Free-plan grant. Runs as supabase_auth_admin (the role GoTrue uses),
-- which gets exactly these two INSERTs, not SECURITY DEFINER.
-- ---------------------------------------------------------------------------------------------

create or replace function public.handle_new_user() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  insert into public.profiles (id, email, name)
  values (
    new.id,
    coalesce(new.email, ''),
    left(coalesce(new.raw_user_meta_data ->> 'name', new.raw_user_meta_data ->> 'full_name', ''), 120)
  )
  on conflict (id) do nothing;

  insert into public.credit_ledger (user_id, amount, reason, ref)
  values (new.id, public.free_plan_credits(), 'signup_grant', 'signup:' || new.id::text)
  on conflict (ref) do nothing;

  return new;
end $$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.free_plan_credits() to supabase_auth_admin;
grant execute on function public.handle_new_user() to supabase_auth_admin;
grant insert on public.profiles, public.credit_ledger to supabase_auth_admin;
-- ON CONFLICT DO NOTHING needs to see the conflicting row's key.
grant select (id) on public.profiles to supabase_auth_admin;
grant select (ref) on public.credit_ledger to supabase_auth_admin;
create policy profiles_auth_admin_insert on public.profiles
  for insert to supabase_auth_admin with check (true);
create policy profiles_auth_admin_select on public.profiles
  for select to supabase_auth_admin using (true);
create policy credit_ledger_auth_admin_insert on public.credit_ledger
  for insert to supabase_auth_admin with check (reason = 'signup_grant' and amount = public.free_plan_credits());
create policy credit_ledger_auth_admin_select on public.credit_ledger
  for select to supabase_auth_admin using (true);

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------------------------
-- Money-moving functions (service role only; SECURITY INVOKER).
-- Each call is one statement from the API route, so it runs in one transaction. A per-user
-- advisory lock serialises concurrent spends so two requests cannot both pass the balance check.
-- ---------------------------------------------------------------------------------------------

create or replace function public.lock_user_credits(p_user_id uuid) returns void
language sql
set search_path = ''
as $$ select pg_advisory_xact_lock(hashtextextended('credits:' || p_user_id::text, 0)) $$;

create or replace function public.user_balance(p_user_id uuid) returns integer
language sql stable
set search_path = ''
as $$ select coalesce(sum(amount), 0)::integer from public.credit_ledger where user_id = p_user_id $$;

-- Debit credits for a non-render action (scene generation, prompt edit, preview).
-- Idempotent on p_ref: a replayed ref returns the existing row and charges nothing.
create or replace function public.spend_credits(
  p_user_id    uuid,
  p_amount     integer,
  p_reason     text,
  p_ref        text,
  p_project_id uuid default null
) returns public.credit_ledger
language plpgsql
set search_path = ''
as $$
declare
  v_row public.credit_ledger;
  v_balance integer;
begin
  if p_amount is null or p_amount <= 0 then
    raise exception 'amount must be positive' using errcode = '22023';
  end if;
  if p_reason not in ('scene_generation', 'prompt_edit', 'preview_render') then
    raise exception 'reason % is not spendable', p_reason using errcode = '22023';
  end if;
  if p_project_id is not null and not exists (
    select 1 from public.projects where id = p_project_id and user_id = p_user_id
  ) then
    raise exception 'project not found' using errcode = 'P0002';
  end if;

  perform public.lock_user_credits(p_user_id);

  select * into v_row from public.credit_ledger where ref = p_ref;
  if found then
    if v_row.user_id <> p_user_id then
      raise exception 'ref belongs to another user' using errcode = '42501';
    end if;
    return v_row;
  end if;

  v_balance := public.user_balance(p_user_id);
  if v_balance < p_amount then
    raise exception 'insufficient_credits: need %, have %', p_amount, v_balance using errcode = 'P0001';
  end if;

  insert into public.credit_ledger (user_id, amount, reason, ref, project_id)
  values (p_user_id, -p_amount, p_reason, p_ref, p_project_id)
  returning * into v_row;
  return v_row;
end $$;

-- Create a render job and debit its cost atomically.
-- Idempotent on (user, p_idempotency_key): a retry returns the existing job, charged once.
create or replace function public.create_render_job(
  p_user_id         uuid,
  p_project_id      uuid,
  p_version_id      uuid,
  p_upload_id       uuid,
  p_kind            public.render_job_kind,
  p_params          jsonb,
  p_cost            integer,
  p_idempotency_key text
) returns public.render_jobs
language plpgsql
set search_path = ''
as $$
declare
  v_job public.render_jobs;
  v_balance integer;
begin
  if p_cost is null or p_cost < 0 then
    raise exception 'cost must be >= 0' using errcode = '22023';
  end if;
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 128 then
    raise exception 'idempotency key required' using errcode = '22023';
  end if;
  if not exists (select 1 from public.projects where id = p_project_id and user_id = p_user_id) then
    raise exception 'project not found' using errcode = 'P0002';
  end if;
  if p_version_id is not null and not exists (
    select 1 from public.scene_versions where id = p_version_id and project_id = p_project_id
  ) then
    raise exception 'version not found' using errcode = 'P0002';
  end if;
  if p_upload_id is not null and not exists (
    select 1 from public.uploads where id = p_upload_id and user_id = p_user_id and status = 'ready'
  ) then
    raise exception 'upload not ready' using errcode = 'P0002';
  end if;

  perform public.lock_user_credits(p_user_id);

  select * into v_job from public.render_jobs
   where user_id = p_user_id and idempotency_key = p_idempotency_key;
  if found then
    return v_job;
  end if;

  v_balance := public.user_balance(p_user_id);
  if v_balance < p_cost then
    raise exception 'insufficient_credits: need %, have %', p_cost, v_balance using errcode = 'P0001';
  end if;

  insert into public.render_jobs (user_id, project_id, version_id, upload_id, kind, params, cost_credits, idempotency_key)
  values (p_user_id, p_project_id, p_version_id, p_upload_id, p_kind, coalesce(p_params, '{}'::jsonb), p_cost, p_idempotency_key)
  returning * into v_job;

  if p_cost > 0 then
    insert into public.credit_ledger (user_id, amount, reason, ref, project_id, job_id)
    values (p_user_id, -p_cost, 'render_final', 'render:' || v_job.id::text, p_project_id, v_job.id);
  end if;

  return v_job;
end $$;

-- Refund a failed or cancelled job's debit. Idempotent: a second call refunds nothing.
-- Returns the credits refunded by this call (0 when already refunded or nothing was charged).
create or replace function public.refund_render_job(p_job_id uuid) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_job public.render_jobs;
  v_charged integer;
  v_inserted integer;
begin
  select * into v_job from public.render_jobs where id = p_job_id for update;
  if not found then
    raise exception 'job not found' using errcode = 'P0002';
  end if;
  if v_job.status not in ('failed', 'cancelled') then
    raise exception 'job % is %, only failed or cancelled jobs are refunded', p_job_id, v_job.status
      using errcode = '22023';
  end if;

  select coalesce(-sum(amount), 0)::integer into v_charged
    from public.credit_ledger where ref = 'render:' || p_job_id::text;
  if v_charged <= 0 then
    return 0;
  end if;

  insert into public.credit_ledger (user_id, amount, reason, ref, project_id, job_id)
  values (v_job.user_id, v_charged, 'render_refund', 'refund:' || p_job_id::text, v_job.project_id, p_job_id)
  on conflict (ref) do nothing;
  get diagnostics v_inserted = row_count;
  return case when v_inserted > 0 then v_charged else 0 end;
end $$;

revoke all on function public.lock_user_credits(uuid) from public, anon, authenticated;
revoke all on function public.user_balance(uuid) from public, anon, authenticated;
revoke all on function public.spend_credits(uuid, integer, text, text, uuid) from public, anon, authenticated;
revoke all on function public.create_render_job(uuid, uuid, uuid, uuid, public.render_job_kind, jsonb, integer, text) from public, anon, authenticated;
revoke all on function public.refund_render_job(uuid) from public, anon, authenticated;
revoke all on function public.handle_new_user() from public, anon, authenticated;
revoke all on function public.credit_ledger_block_update() from public, anon, authenticated;

grant execute on function public.lock_user_credits(uuid) to service_role;
grant execute on function public.user_balance(uuid) to service_role;
grant execute on function public.spend_credits(uuid, integer, text, text, uuid) to service_role;
grant execute on function public.create_render_job(uuid, uuid, uuid, uuid, public.render_job_kind, jsonb, integer, text) to service_role;
grant execute on function public.refund_render_job(uuid) to service_role;
