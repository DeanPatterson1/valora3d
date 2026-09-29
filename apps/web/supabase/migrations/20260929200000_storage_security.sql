-- Valora3D storage + render hardening (sec-storage lane, 2026-09-29). Fixes from the final security review:
--
--   H1/H2  storage_purge_queue: every R2 object a deleted row owned is queued for deletion IN THE SAME
--          TRANSACTION as the delete (row triggers on uploads and render_jobs), and the account route queues the
--          owner's whole prefixes. The cron sweep drains the queue, so a delete is eventually complete even after
--          the rows cascade away and even if R2 was down at the time.
--   H2     Projects are deleted only through DELETE /api/projects/:id (the service role): `authenticated` loses
--          DELETE on projects. Daily caps count usage_events, an append-only counter that no project delete
--          cascades away, instead of the deletable uploads / render_jobs rows.
--   L8     The upload cap (create_upload) and the render caps (create_render_job) are counted under the per-user
--          lock, so concurrent requests cannot exceed them.
--   M1     create_render_job accepts only the clip lengths the price assumes (8, 10, 12 s), also when pinned in
--          the prompt (the worker's director lets a prompt pin beat params.duration), and no 60 fps pin.
--   M2     finish_render_job v3 can keep a fee (an input-caused failure) and counts those failures; a user with
--          too many input-caused failures today cannot start another render until tomorrow.
--   M3     request_render_cancel records the user's cancel (and whether the GPU had started) BEFORE the route
--          calls RunPod; finish_render_job never refunds a cancel requested after the start, whoever lands the
--          terminal transition. claim_render_poll claims the 10 s poll throttle atomically.
--   L7     profiles.email follows auth.users.email (the render-ready mail reads it).
-- Rules from the init migration hold: RLS on every table, service role only for writes, SECURITY INVOKER,
-- search_path ''. Earlier migrations are never edited.

-- ---------------------------------------------------------------------------------------------
-- Usage counter (append-only; survives project deletion).
-- ---------------------------------------------------------------------------------------------

create table public.usage_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users (id) on delete cascade,
  kind       text not null check (kind in ('upload', 'render', 'input_failure')),
  -- The upload or job this counts (no FK: the count must outlive the row).
  ref        uuid,
  created_at timestamptz not null default now()
);
create index usage_events_user_kind_idx on public.usage_events (user_id, kind, created_at desc);

create or replace function public.usage_events_block_update() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'usage_events is append-only' using errcode = '42501';
end $$;
create trigger usage_events_append_only before update on public.usage_events
  for each row execute function public.usage_events_block_update();

alter table public.usage_events enable row level security;
revoke all on public.usage_events from anon, authenticated;
revoke all on sequence public.usage_events_id_seq from anon, authenticated;
grant all on public.usage_events to service_role;
-- No policies: users never read or write it.

-- What was already counted by the old row-based caps keeps counting for the rest of its day.
insert into public.usage_events (user_id, kind, ref, created_at)
select user_id, 'upload', id, created_at from public.uploads
 where source = 'upload' and created_at > now() - interval '24 hours';
insert into public.usage_events (user_id, kind, ref, created_at)
select user_id, 'render', id, created_at from public.render_jobs
 where created_at > now() - interval '24 hours';

-- Abuse ceilings, not plan limits. Mirrored in lib/usageLimits.ts (lib/server/storagePurge.test.ts pins both).
create or replace function public.upload_daily_cap() returns integer
language sql immutable parallel safe set search_path = '' as $$ select 30 $$;
create or replace function public.render_daily_cap() returns integer
language sql immutable parallel safe set search_path = '' as $$ select 50 $$;
create or replace function public.input_failure_daily_cap() returns integer
language sql immutable parallel safe set search_path = '' as $$ select 5 $$;

create or replace function public.usage_count(p_user_id uuid, p_kind text) returns integer
language sql stable
set search_path = ''
as $$
  select count(*)::integer from public.usage_events
   where user_id = p_user_id and kind = p_kind and created_at > now() - interval '24 hours'
$$;

-- Old events are useless to a 24 h window.
create or replace function public.prune_usage_events() returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  delete from public.usage_events where created_at < now() - interval '7 days';
  get diagnostics v_count = row_count;
  return v_count;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Uploads: the row, its presigned key and the daily cap in one locked transaction.
-- ---------------------------------------------------------------------------------------------

--   'rate_limited: uploads' (P0001) the daily upload cap is reached
--   'project not found'     (P0002)
create or replace function public.create_upload(
  p_user_id    uuid,
  p_project_id uuid,
  p_upload_id  uuid,
  p_r2_key     text,
  p_file_name  text,
  p_size_bytes bigint,
  p_sha256     text
) returns public.uploads
language plpgsql
set search_path = ''
as $$
declare
  v_upload public.uploads;
begin
  if not exists (select 1 from public.projects where id = p_project_id and user_id = p_user_id) then
    raise exception 'project not found' using errcode = 'P0002';
  end if;
  perform public.lock_user_credits(p_user_id);
  if public.usage_count(p_user_id, 'upload') >= public.upload_daily_cap() then
    raise exception 'rate_limited: uploads' using errcode = 'P0001';
  end if;
  insert into public.uploads (id, user_id, project_id, source, file_name, format, r2_key, size_bytes, sha256, status)
  values (p_upload_id, p_user_id, p_project_id, 'upload', p_file_name, 'glb', p_r2_key, p_size_bytes, p_sha256, 'pending')
  returning * into v_upload;
  insert into public.usage_events (user_id, kind, ref) values (p_user_id, 'upload', v_upload.id);
  return v_upload;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Storage purge queue.
-- ---------------------------------------------------------------------------------------------

-- One R2 object key or prefix to delete. Only shapes the site itself writes are accepted, always inside the
-- owner's own prefix, so a bad row can never widen a delete (an empty prefix would list the whole bucket).
create table public.storage_purge_queue (
  id            bigint generated always as identity primary key,
  -- No FK on purpose: the owner (and every row that pointed at the objects) may already be gone.
  user_id       uuid not null,
  target        text not null,
  reason        text not null check (reason in ('account_deleted', 'project_deleted', 'upload_deleted', 'render_deleted')),
  -- Not before this moment: a late sweep after every presigned PUT the owner still held has expired.
  not_before    timestamptz not null default now(),
  attempts      integer not null default 0 check (attempts >= 0),
  claimed_at    timestamptz,
  claimed_until timestamptz,
  last_error    text check (last_error is null or char_length(last_error) <= 500),
  created_at    timestamptz not null default now(),
  constraint storage_purge_target_shape check (
    target ~ '^[ur]/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/$'
    or target ~ '^r/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/$'
    or target ~ '^u/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.glb$'
  ),
  constraint storage_purge_owner_prefix check (split_part(target, '/', 2) = user_id::text),
  unique (target, not_before)
);
create index storage_purge_due_idx on public.storage_purge_queue (not_before, id);
create index storage_purge_user_idx on public.storage_purge_queue (user_id, not_before);

alter table public.storage_purge_queue enable row level security;
revoke all on public.storage_purge_queue from anon, authenticated;
revoke all on sequence public.storage_purge_queue_id_seq from anon, authenticated;
grant all on public.storage_purge_queue to service_role;
-- No policies: users never read or write it.

-- How long after a submit the worker may still PUT a job's outputs: the presigned PUT lifetime
-- (ttl + executionTimeout + 30 min margin, lib/render/contract.ts presignLifetimes / TIER_POLICY).
create or replace function public.render_put_window(p_kind public.render_job_kind) returns interval
language sql immutable parallel safe
set search_path = ''
as $$
  select case p_kind when 'preview' then interval '24 hours 50 minutes' else interval '26 hours 30 minutes' end
$$;

-- An upload's presigned PUT lives 10 minutes (R2Storage.presignPut); the late sweep waits 15.
create or replace function public.upload_put_window() returns interval
language sql immutable parallel safe set search_path = '' as $$ select interval '15 minutes' $$;

create or replace function public.enqueue_storage_purge(
  p_user_id    uuid,
  p_target     text,
  p_reason     text,
  p_not_before timestamptz default now()
) returns void
language sql
set search_path = ''
as $$
  insert into public.storage_purge_queue (user_id, target, reason, not_before)
  values (p_user_id, p_target, p_reason, coalesce(p_not_before, now()))
  on conflict (target, not_before) do nothing
$$;

-- True when an account-level late sweep is already queued for this prefix: it covers every object below it,
-- so per-row triggers during the account's cascade need not queue their own.
create or replace function public.storage_purge_covered(p_prefix text) returns boolean
language sql stable
set search_path = ''
as $$
  select exists (select 1 from public.storage_purge_queue where target = p_prefix and not_before > now())
$$;

create or replace function public.enqueue_deleted_upload() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.source = 'upload' and old.purged_at is null and old.r2_key is not null
     and old.r2_key ~ '^u/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.glb$'
     and split_part(old.r2_key, '/', 2) = old.user_id::text
     and not public.storage_purge_covered('u/' || old.user_id::text || '/') then
    perform public.enqueue_storage_purge(old.user_id, old.r2_key, 'upload_deleted', now());
    if old.status = 'pending' then
      -- The browser may still PUT with its presigned URL after the row is gone.
      perform public.enqueue_storage_purge(old.user_id, old.r2_key, 'upload_deleted', now() + public.upload_put_window());
    end if;
  end if;
  return old;
end $$;

create or replace function public.enqueue_deleted_render_job() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_prefix text := 'r/' || old.user_id::text || '/' || old.id::text || '/';
begin
  if old.expired_at is null and not public.storage_purge_covered('r/' || old.user_id::text || '/') then
    perform public.enqueue_storage_purge(old.user_id, v_prefix, 'render_deleted', now());
    if old.status in ('queued', 'running') then
      -- A worker still holding the output PUT URLs may write after the row is gone.
      perform public.enqueue_storage_purge(old.user_id, v_prefix, 'render_deleted',
                                           coalesce(old.submitted_at, now()) + public.render_put_window(old.kind));
    end if;
  end if;
  return old;
end $$;

create trigger uploads_enqueue_purge after delete on public.uploads
  for each row execute function public.enqueue_deleted_upload();
create trigger render_jobs_enqueue_purge after delete on public.render_jobs
  for each row execute function public.enqueue_deleted_render_job();

-- Claims due entries (optionally one owner's) for up to 5 minutes; a crashed drain's claim simply lapses.
create or replace function public.claim_storage_purges(p_limit integer default 50, p_user_id uuid default null)
returns table (id bigint, user_id uuid, target text)
language plpgsql
set search_path = ''
as $$
begin
  return query
  with due as (
    select q.id from public.storage_purge_queue q
     where q.not_before <= now()
       and (q.claimed_until is null or q.claimed_until < now())
       and (p_user_id is null or q.user_id = p_user_id)
     order by q.not_before, q.id
     limit greatest(1, least(coalesce(p_limit, 50), 500))
     for update skip locked
  )
  update public.storage_purge_queue q
     set claimed_at = now(), claimed_until = now() + interval '5 minutes', attempts = q.attempts + 1
    from due
   where q.id = due.id
  returning q.id, q.user_id, q.target;
end $$;

-- Done: removes the entries, plus due entries a completed prefix already covered (queued before it was listed).
create or replace function public.complete_storage_purges(p_ids bigint[]) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  delete from public.storage_purge_queue s
   using public.storage_purge_queue c
   where c.id = any (p_ids)
     and c.target like '%/'
     and c.claimed_at is not null
     and s.id <> all (p_ids)
     and s.user_id = c.user_id
     and left(s.target, char_length(c.target)) = c.target
     and s.created_at <= c.claimed_at
     and s.not_before <= c.claimed_at;
  delete from public.storage_purge_queue where id = any (p_ids);
  get diagnostics v_count = row_count;
  return v_count;
end $$;

-- Not done (an R2 error, or the work budget ran out mid-prefix): back off and try again later.
create or replace function public.release_storage_purges(p_ids bigint[], p_error text) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  update public.storage_purge_queue
     set claimed_until = null,
         not_before = greatest(not_before, now() + make_interval(mins => least(60, 5 * attempts))),
         last_error = left(p_error, 500)
   where id = any (p_ids);
  get diagnostics v_count = row_count;
  return v_count;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Projects: deleted only through the API route (service role), which cleans R2.
-- ---------------------------------------------------------------------------------------------

drop policy projects_delete_own on public.projects;
revoke delete on public.projects from authenticated;
-- Children never had user DELETE (uploads, render_jobs, render_shares: select only; scene_versions: revoked by
-- 20260929100000). Say it again so a later grant cannot quietly reopen the cascade path.
revoke delete, truncate on public.uploads, public.render_jobs, public.scene_versions, public.render_shares
  from anon, authenticated;
revoke truncate on public.projects from anon, authenticated;

-- ---------------------------------------------------------------------------------------------
-- Render jobs: cancel intent, fees, the poll claim.
-- ---------------------------------------------------------------------------------------------

alter table public.render_jobs
  -- Set by the cancel route BEFORE it calls RunPod.
  add column cancel_requested_at timestamptz,
  -- The GPU had started when the cancel was asked for: no refund, whichever caller finishes the job.
  add column cancel_after_start  boolean not null default false,
  -- Whose fault a failure was (lib/render/failurePolicy.ts): 'input' keeps a fee, 'infra' refunds in full.
  add column failure_fault       text check (failure_fault is null or failure_fault in ('input', 'infra')),
  -- Credits kept on a failed job (an input-caused failure's fee).
  add column fee_credits         integer not null default 0 check (fee_credits >= 0);

-- Records the cancel intent. p_started: the route saw the GPU running (RunPod IN_PROGRESS). Also true when the
-- row itself says so. Idempotent; never clears an earlier "started".
create or replace function public.request_render_cancel(p_job_id uuid, p_started boolean)
returns public.render_jobs
language plpgsql
set search_path = ''
as $$
declare
  v_job public.render_jobs;
begin
  update public.render_jobs
     set cancel_requested_at = coalesce(cancel_requested_at, now()),
         cancel_after_start = cancel_after_start or coalesce(p_started, false)
                              or started_at is not null or status = 'running'
   where id = p_job_id and status in ('queued', 'running')
  returning * into v_job;
  return v_job;
end $$;

-- The 10 s poll throttle, claimed atomically: true for exactly one caller per window.
create or replace function public.claim_render_poll(p_job_id uuid, p_min_seconds integer) returns boolean
language plpgsql
set search_path = ''
as $$
declare
  v_moved integer;
begin
  update public.render_jobs
     set last_polled_at = now()
   where id = p_job_id
     and status in ('queued', 'running')
     and (last_polled_at is null or last_polled_at <= now() - make_interval(secs => greatest(0, p_min_seconds)));
  get diagnostics v_moved = row_count;
  return v_moved > 0;
end $$;

-- ---------------------------------------------------------------------------------------------
-- finish_render_job v3: a fee on input-caused failures, and the cancel rule. The signature gains p_fee, so the
-- old one is dropped (callers passing the 8 named arguments still resolve through the default).
-- ---------------------------------------------------------------------------------------------

drop function public.finish_render_job(uuid, text, public.render_job_status, text, text, boolean, jsonb, boolean);

create function public.finish_render_job(
  p_job_id     uuid,
  p_runpod_id  text,
  p_status     public.render_job_status,
  p_error      text,
  p_error_code text,
  p_retryable  boolean,
  p_result     jsonb,
  p_refund     boolean,
  p_fee        integer default 0
) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_job public.render_jobs;
  v_refund integer := 0;
  v_charged integer;
  v_inserted integer;
  v_fault text;
  r jsonb := coalesce(p_result, '{}'::jsonb);
begin
  if p_status not in ('succeeded', 'failed', 'cancelled') then
    raise exception 'finish_render_job needs a terminal status, got %', p_status using errcode = '22023';
  end if;
  if p_status = 'succeeded' and p_refund then
    raise exception 'a succeeded job is never refunded' using errcode = '22023';
  end if;
  if p_fee is null or p_fee < 0 then
    raise exception 'fee must be >= 0' using errcode = '22023';
  end if;
  v_fault := case when p_status <> 'succeeded' and r ->> 'fault' in ('input', 'infra') then r ->> 'fault' end;

  update public.render_jobs set
    status         = p_status,
    error          = left(p_error, 300),
    error_code     = p_error_code,
    retryable      = p_retryable,
    failure_fault  = v_fault,
    runpod_status  = coalesce(r ->> 'runpod_status', runpod_status),
    stage          = coalesce(r ->> 'stage', stage),
    frame          = coalesce((r ->> 'frame')::integer, frame),
    total_frames   = coalesce((r ->> 'total_frames')::integer, total_frames),
    outputs        = coalesce(r -> 'outputs', outputs),
    video          = coalesce(r -> 'video', video),
    timings        = coalesce(r -> 'timings', timings),
    warnings       = coalesce(r -> 'warnings', warnings),
    watermarked    = case when jsonb_typeof(r -> 'watermarked') = 'boolean'
                          then (r ->> 'watermarked')::boolean else watermarked end,
    render_seconds = coalesce((r ->> 'render_seconds')::double precision, render_seconds),
    gpu_seconds    = coalesce((r ->> 'gpu_seconds')::double precision, gpu_seconds),
    delay_ms       = coalesce((r ->> 'delay_ms')::bigint, delay_ms),
    execution_ms   = coalesce((r ->> 'execution_ms')::bigint, execution_ms),
    output_keys    = case when jsonb_typeof(r -> 'output_keys') = 'array'
                          then array(select jsonb_array_elements_text(r -> 'output_keys'))
                          else output_keys end,
    last_polled_at = now(),
    finished_at    = now()
  where id = p_job_id
    and status in ('queued', 'running')
    and runpod_id is not distinct from p_runpod_id
  returning * into v_job;
  if not found then
    return -1;
  end if;

  if v_fault = 'input' then
    insert into public.usage_events (user_id, kind, ref) values (v_job.user_id, 'input_failure', v_job.id);
  end if;

  -- A cancel the user asked for after the GPU started is never refunded, whichever caller (the cancel route,
  -- a concurrent poll that saw RunPod's CANCELLED, the webhook, the sweeper) lands this transition.
  if p_refund and not (v_job.cancel_requested_at is not null
                       and (v_job.cancel_after_start or v_job.started_at is not null)) then
    select coalesce(-sum(amount), 0)::integer into v_charged
      from public.credit_ledger where ref = 'render:' || p_job_id::text;
    if v_charged > 0 and v_charged > least(p_fee, v_charged) then
      insert into public.credit_ledger (user_id, amount, reason, ref, project_id, job_id)
      values (v_job.user_id, v_charged - least(p_fee, v_charged), 'render_refund', 'refund:' || p_job_id::text,
              v_job.project_id, p_job_id)
      on conflict (ref) do nothing;
      get diagnostics v_inserted = row_count;
      if v_inserted > 0 then
        v_refund := v_charged - least(p_fee, v_charged);
      end if;
    end if;
    update public.render_jobs
       set refunded_credits = v_refund,
           fee_credits = case when v_charged > 0 then least(p_fee, v_charged) else 0 end
     where id = p_job_id;
  end if;
  return v_refund;
end $$;

revoke all on function public.finish_render_job(uuid, text, public.render_job_status, text, text, boolean, jsonb, boolean, integer)
  from public, anon, authenticated;
grant execute on function public.finish_render_job(uuid, text, public.render_job_status, text, text, boolean, jsonb, boolean, integer)
  to service_role;

-- ---------------------------------------------------------------------------------------------
-- create_render_job v3 (same signature, so its grants stand).
-- ---------------------------------------------------------------------------------------------

-- The clip format a prompt pins, as the worker's director reads it (Rendering-worker engine/director/intent.py
-- _DUR / _FPS; a prompt pin beats params.duration there). True when it stays inside what the price assumes:
-- no duration pin or 8..12 s, and no 60 fps pin. lib/render/params.ts promptFormatIssue mirrors it.
create or replace function public.render_prompt_format_ok(p_prompt text) returns boolean
language plpgsql immutable
set search_path = ''
as $$
declare
  v_text text := lower(coalesce(p_prompt, ''));
  v_duration text;
begin
  v_duration := substring(v_text from '(?<![0-9.])([0-9]{1,3}(?:\.[0-9]+)?)[[:space:]-]*(?:s|sec|secs|second|seconds)\y');
  if v_duration is not null and v_duration::numeric not between 8 and 12 then
    return false;
  end if;
  if v_text ~ '\y60[[:space:]]*fps\y' then
    return false;
  end if;
  return true;
end $$;

--   'invalid duration'          (22023) params.duration is not 8, 10 or 12
--   'prompt_format'             (22023) the prompt pins a length or frame rate outside the price
--   'rate_limited: renders'     (P0001) the daily render cap is reached
--   'rate_limited: input_failures' (P0001) too many renders failed on their input today
--   plus v2's plan_required / too_many_active / insufficient_credits.
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
  v_limits record;
  v_active integer;
begin
  if p_cost is null or p_cost < 0 then
    raise exception 'cost must be >= 0' using errcode = '22023';
  end if;
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 128 then
    raise exception 'idempotency key required' using errcode = '22023';
  end if;
  if p_params ? 'watermark' then
    -- The watermark comes from the plan (render_jobs.watermark), never from the request.
    raise exception 'params.watermark is set by the server' using errcode = '22023';
  end if;
  -- The price is flat per tier and assumes the studio's clip lengths.
  if p_params ? 'duration' and (case when jsonb_typeof(p_params -> 'duration') = 'number'
                                     then (p_params ->> 'duration')::numeric not in (8, 10, 12)
                                     else true end) then
    raise exception 'invalid duration' using errcode = '22023';
  end if;
  if not public.render_prompt_format_ok(p_params ->> 'prompt') then
    raise exception 'prompt_format' using errcode = '22023';
  end if;
  if not exists (select 1 from public.projects where id = p_project_id and user_id = p_user_id) then
    raise exception 'project not found' using errcode = 'P0002';
  end if;
  if p_version_id is not null and not exists (
    select 1 from public.scene_versions where id = p_version_id and project_id = p_project_id
  ) then
    raise exception 'version not found' using errcode = 'P0002';
  end if;
  perform public.lock_user_credits(p_user_id);

  select * into v_job from public.render_jobs
   where user_id = p_user_id and idempotency_key = p_idempotency_key;
  if found then
    -- A retry must be the same request; reusing a key for a different job is a client bug.
    if v_job.project_id <> p_project_id or v_job.cost_credits <> p_cost
       or v_job.params is distinct from coalesce(p_params, '{}'::jsonb) then
      raise exception 'idempotency key reused with different parameters' using errcode = '23505';
    end if;
    return v_job;
  end if;

  -- Abuse ceilings, counted under the lock from the append-only counter (deleting a project resets nothing).
  if public.usage_count(p_user_id, 'render') >= public.render_daily_cap() then
    raise exception 'rate_limited: renders' using errcode = 'P0001';
  end if;
  if public.usage_count(p_user_id, 'input_failure') >= public.input_failure_daily_cap() then
    raise exception 'rate_limited: input_failures' using errcode = 'P0001';
  end if;

  -- Marks the model as used, row-locked: this conflicts with expire_uploads' FOR UPDATE, so the sweep either
  -- skips this model or has already claimed it (then 0 rows here and the render is refused).
  if p_upload_id is not null then
    update public.uploads set last_used_at = now()
     where id = p_upload_id and user_id = p_user_id and status = 'ready' and expired_at is null;
    if not found then
      raise exception 'upload not ready' using errcode = 'P0002';
    end if;
  end if;

  select * into v_limits from public.user_plan_limits(p_user_id);
  if not (p_kind::text = any (v_limits.tiers)) then
    raise exception 'plan_required: %', p_kind using errcode = 'P0001';
  end if;
  select count(*) into v_active from public.render_jobs
   where user_id = p_user_id and status in ('queued', 'running');
  if v_active >= v_limits.max_active_jobs then
    raise exception 'too_many_active: max %', v_limits.max_active_jobs using errcode = 'P0001';
  end if;

  v_balance := public.user_balance(p_user_id);
  if v_balance < p_cost then
    raise exception 'insufficient_credits: need %, have %', p_cost, v_balance using errcode = 'P0001';
  end if;

  insert into public.render_jobs (user_id, project_id, version_id, upload_id, kind, params, cost_credits, idempotency_key,
                                  watermark, retention_days)
  values (p_user_id, p_project_id, p_version_id, p_upload_id, p_kind, coalesce(p_params, '{}'::jsonb), p_cost, p_idempotency_key,
          v_limits.watermark, v_limits.retention_days)
  returning * into v_job;
  insert into public.usage_events (user_id, kind, ref) values (p_user_id, 'render', v_job.id);

  if p_cost > 0 then
    insert into public.credit_ledger (user_id, amount, reason, ref, project_id, job_id)
    values (p_user_id, -p_cost, case p_kind when 'preview' then 'render_preview' else 'render_final' end,
            'render:' || v_job.id::text, p_project_id, v_job.id);
  end if;

  return v_job;
end $$;

-- ---------------------------------------------------------------------------------------------
-- profiles.email follows the auth email (L7). GoTrue runs the trigger as supabase_auth_admin.
-- ---------------------------------------------------------------------------------------------

create or replace function public.handle_user_email_changed() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  update public.profiles set email = coalesce(new.email, '') where id = new.id;
  return new;
end $$;

grant update (email) on public.profiles to supabase_auth_admin;
create policy profiles_auth_admin_update on public.profiles
  for update to supabase_auth_admin using (true) with check (true);

create trigger on_auth_user_email_changed
  after update of email on auth.users
  for each row when (old.email is distinct from new.email)
  execute function public.handle_user_email_changed();

-- Profiles written before this trigger existed.
update public.profiles p set email = u.email
  from auth.users u
 where u.id = p.id and u.email is not null and p.email is distinct from u.email;

-- ---------------------------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------------------------

revoke all on function public.usage_events_block_update() from public, anon, authenticated;
revoke all on function public.upload_daily_cap() from public, anon, authenticated;
revoke all on function public.render_daily_cap() from public, anon, authenticated;
revoke all on function public.input_failure_daily_cap() from public, anon, authenticated;
revoke all on function public.usage_count(uuid, text) from public, anon, authenticated;
revoke all on function public.prune_usage_events() from public, anon, authenticated;
revoke all on function public.create_upload(uuid, uuid, uuid, text, text, bigint, text) from public, anon, authenticated;
revoke all on function public.render_put_window(public.render_job_kind) from public, anon, authenticated;
revoke all on function public.upload_put_window() from public, anon, authenticated;
revoke all on function public.enqueue_storage_purge(uuid, text, text, timestamptz) from public, anon, authenticated;
revoke all on function public.storage_purge_covered(text) from public, anon, authenticated;
revoke all on function public.enqueue_deleted_upload() from public, anon, authenticated;
revoke all on function public.enqueue_deleted_render_job() from public, anon, authenticated;
revoke all on function public.claim_storage_purges(integer, uuid) from public, anon, authenticated;
revoke all on function public.complete_storage_purges(bigint[]) from public, anon, authenticated;
revoke all on function public.release_storage_purges(bigint[], text) from public, anon, authenticated;
revoke all on function public.request_render_cancel(uuid, boolean) from public, anon, authenticated;
revoke all on function public.claim_render_poll(uuid, integer) from public, anon, authenticated;
revoke all on function public.render_prompt_format_ok(text) from public, anon, authenticated;
revoke all on function public.handle_user_email_changed() from public, anon, authenticated;

grant execute on function public.upload_daily_cap() to service_role;
grant execute on function public.render_daily_cap() to service_role;
grant execute on function public.input_failure_daily_cap() to service_role;
grant execute on function public.usage_count(uuid, text) to service_role;
grant execute on function public.prune_usage_events() to service_role;
grant execute on function public.create_upload(uuid, uuid, uuid, text, text, bigint, text) to service_role;
grant execute on function public.render_put_window(public.render_job_kind) to service_role;
grant execute on function public.upload_put_window() to service_role;
grant execute on function public.enqueue_storage_purge(uuid, text, text, timestamptz) to service_role;
grant execute on function public.storage_purge_covered(text) to service_role;
grant execute on function public.claim_storage_purges(integer, uuid) to service_role;
grant execute on function public.complete_storage_purges(bigint[]) to service_role;
grant execute on function public.release_storage_purges(bigint[], text) to service_role;
grant execute on function public.request_render_cancel(uuid, boolean) to service_role;
grant execute on function public.claim_render_poll(uuid, integer) to service_role;
grant execute on function public.render_prompt_format_ok(text) to service_role;
grant execute on function public.handle_user_email_changed() to supabase_auth_admin;
