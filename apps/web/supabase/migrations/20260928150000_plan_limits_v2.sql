-- Valora3D plan limits v2 + render/billing integration (2026-09-28).
--
-- Makes every plan claim something the system actually does, and enforces it where the credits move:
--   * plan_limits v2: the worker renders two tiers only (preview = 540p short side, final = 1080p); there is
--     no 4K and RunPod has no per-job priority, so `max_resolution` is 540p / 1080p and `priority` is gone.
--     New: `tiers` (what a plan may render), `max_active_jobs` (renders queued or running at once) and
--     `plan_rank` (Free < Creator < Pro, for upgrade/downgrade decisions only; not a GPU priority).
--     Mirrors PLAN_LIMITS in lib/pricing.ts (lib/billing/billing.test.ts pins both).
--   * create_render_job enforces the plan under the credit lock: tier allowed, concurrent jobs, and stamps
--     the job with `watermark` and `retention_days` from the plan at creation. The ledger reason follows
--     the tier (render_preview / render_final); the ref stays 'render:<job>' so idempotency is unchanged.
--   * finish_render_job also records `watermarked` (what the worker says it actually drew).
--   * Retention: expired_render_outputs() / mark_render_outputs_expired() and expire_uploads() /
--     mark_uploads_purged() are the sweep's batch API (POST /api/renders/sweep, cron). Earlier migrations
--     are never edited; everything here replaces or extends them.
-- Rules from the init migration hold: RLS on, service role only for writes, SECURITY INVOKER, search_path ''.

-- ---------------------------------------------------------------------------------------------
-- Plan limits v2 (the OUT columns change, so drop and recreate).
-- ---------------------------------------------------------------------------------------------

drop function public.user_plan_limits(uuid);
drop function public.plan_limits(public.plan_tier);

create function public.plan_limits(p_plan public.plan_tier)
returns table (max_resolution text, tiers text[], watermark boolean, retention_days integer, max_active_jobs integer, plan_rank integer)
language sql immutable parallel safe
set search_path = ''
as $$
  select l.max_resolution, l.tiers, l.watermark, l.retention_days, l.max_active_jobs, l.plan_rank from (values
    ('free'::public.plan_tier,    '540p',  array['preview']::text[],          true,  7,  1, 0),
    ('creator'::public.plan_tier, '1080p', array['preview', 'final']::text[], false, 30, 1, 1),
    ('pro'::public.plan_tier,     '1080p', array['preview', 'final']::text[], false, 90, 3, 2)
  ) as l(plan, max_resolution, tiers, watermark, retention_days, max_active_jobs, plan_rank)
  where l.plan = p_plan
$$;

-- Limits for a user's live entitlement (user_plan: active/trialing or paid through, else Free).
create function public.user_plan_limits(p_user_id uuid)
returns table (plan public.plan_tier, max_resolution text, tiers text[], watermark boolean, retention_days integer,
               max_active_jobs integer, plan_rank integer)
language sql stable
set search_path = ''
as $$
  select p.plan, l.max_resolution, l.tiers, l.watermark, l.retention_days, l.max_active_jobs, l.plan_rank
  from (select public.user_plan(p_user_id) as plan) p
  cross join lateral public.plan_limits(p.plan) l
$$;

revoke all on function public.plan_limits(public.plan_tier) from public, anon;
revoke all on function public.user_plan_limits(uuid) from public, anon, authenticated;
grant execute on function public.plan_limits(public.plan_tier) to authenticated, service_role;
grant execute on function public.user_plan_limits(uuid) to service_role;

-- ---------------------------------------------------------------------------------------------
-- Columns
-- ---------------------------------------------------------------------------------------------

alter table public.render_jobs
  -- Asked of the worker (params.watermark), from the plan at creation. Never from the browser.
  add column watermark      boolean not null default false,
  -- What the worker reports it actually drew (null until it succeeds).
  add column watermarked    boolean,
  -- Days the outputs are kept after the job finishes, from the plan at creation.
  -- Existing rows (made before this migration) get the longest retention, so no paid render is cut short;
  -- create_render_job always sets it explicitly.
  add column retention_days smallint not null default 90 check (retention_days between 1 and 3650),
  -- Set once the outputs were deleted from R2; the row stays as history.
  add column expired_at     timestamptz;

-- The retention scan: finished jobs whose outputs are still stored.
create index render_jobs_retention_idx on public.render_jobs (finished_at)
  where expired_at is null and status in ('succeeded', 'failed', 'cancelled');

alter table public.uploads
  -- Claimed by the retention sweep: hidden from new renders from this moment.
  add column expired_at timestamptz,
  -- The R2 object is gone. expired_at without purged_at = the delete is still to do (or to retry).
  add column purged_at  timestamptz,
  -- Last time a render was created from this model (written by create_render_job under a row lock, so the
  -- retention sweep can never claim a model a render is being created from).
  add column last_used_at timestamptz,
  add constraint uploads_purged_after_expired check (purged_at is null or expired_at is not null);

create index uploads_retention_idx on public.uploads (created_at)
  where source = 'upload' and purged_at is null;
create index render_jobs_upload_idx on public.render_jobs (upload_id, created_at desc);

-- ---------------------------------------------------------------------------------------------
-- Ledger: a preview debit is its own reason.
-- ---------------------------------------------------------------------------------------------

alter table public.credit_ledger drop constraint credit_ledger_reason_check;
alter table public.credit_ledger add constraint credit_ledger_reason_check check (reason in (
  'signup_grant', 'plan_grant', 'pack_purchase',
  'scene_generation', 'prompt_edit', 'preview_render', 'render_preview', 'render_final',
  'render_refund', 'admin_adjustment', 'billing_reversal'));

-- ---------------------------------------------------------------------------------------------
-- create_render_job v2 (same signature, so the grants from the init migration stand).
-- ---------------------------------------------------------------------------------------------

-- Creates the job and debits its cost in one transaction, enforcing the caller's live plan under the
-- per-user credit lock (so two concurrent requests cannot both pass the concurrency check):
--   'plan_required: <tier>'       (P0001) the plan does not include this tier
--   'too_many_active: max <n>'    (P0001) the plan's concurrent-render limit is reached
--   'insufficient_credits: ...'   (P0001) as before; a negative balance refuses everything
-- A replayed idempotency key returns the original job before any limit is counted again.
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

  if p_cost > 0 then
    insert into public.credit_ledger (user_id, amount, reason, ref, project_id, job_id)
    values (p_user_id, -p_cost, case p_kind when 'preview' then 'render_preview' else 'render_final' end,
            'render:' || v_job.id::text, p_project_id, v_job.id);
  end if;

  return v_job;
end $$;

-- ---------------------------------------------------------------------------------------------
-- finish_render_job v2: also records `watermarked` from the worker's output (same signature).
-- ---------------------------------------------------------------------------------------------

create or replace function public.finish_render_job(
  p_job_id     uuid,
  p_runpod_id  text,
  p_status     public.render_job_status,
  p_error      text,
  p_error_code text,
  p_retryable  boolean,
  p_result     jsonb,
  p_refund     boolean
) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_moved integer;
  v_refund integer := 0;
  r jsonb := coalesce(p_result, '{}'::jsonb);
begin
  if p_status not in ('succeeded', 'failed', 'cancelled') then
    raise exception 'finish_render_job needs a terminal status, got %', p_status using errcode = '22023';
  end if;
  if p_status = 'succeeded' and p_refund then
    raise exception 'a succeeded job is never refunded' using errcode = '22023';
  end if;

  update public.render_jobs set
    status         = p_status,
    error          = left(p_error, 300),
    error_code     = p_error_code,
    retryable      = p_retryable,
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
    and runpod_id is not distinct from p_runpod_id;
  get diagnostics v_moved = row_count;
  if v_moved = 0 then
    return -1;
  end if;

  if p_refund then
    v_refund := public.refund_render_job(p_job_id);
    update public.render_jobs set refunded_credits = v_refund where id = p_job_id;
  end if;
  return v_refund;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Retention
-- ---------------------------------------------------------------------------------------------

-- Finished jobs whose retention (stamped at creation) has run out and whose outputs are still stored.
-- Failed and cancelled jobs are included: a partial upload may sit at the output keys. The caller deletes
-- r/<user_id>/<job_id>/{video.mp4,poster.jpg} and then calls mark_render_outputs_expired().
create or replace function public.expired_render_outputs(p_limit integer default 100)
returns table (job_id uuid, user_id uuid)
language sql stable
set search_path = ''
as $$
  select j.id, j.user_id
    from public.render_jobs j
   where j.expired_at is null
     and j.status in ('succeeded', 'failed', 'cancelled')
     and coalesce(j.finished_at, j.updated_at) + make_interval(days => j.retention_days) <= now()
   order by j.finished_at nulls first
   limit greatest(1, least(coalesce(p_limit, 100), 500))
$$;

-- Marks jobs whose outputs were deleted. Idempotent; returns the rows that changed.
create or replace function public.mark_render_outputs_expired(p_job_ids uuid[])
returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  update public.render_jobs
     set expired_at = now(), output_keys = '{}'
   where id = any (p_job_ids)
     and expired_at is null
     and status in ('succeeded', 'failed', 'cancelled');
  get diagnostics v_count = row_count;
  return v_count;
end $$;

-- Claims uploaded models past retention and returns the ones whose R2 object still has to be deleted
-- (newly claimed first, then earlier claims whose delete failed). A model expires when the owner's plan
-- retention has passed since it was last used (uploaded, or last rendered from), never while a render of
-- it is queued or running. The retention is the longest of the current plan and any paid plan whose paid
-- period ended less than 30 days ago, so a failed renewal does not delete a paying user's models before
-- the payment is retried. A claimed upload is 'rejected' with reason 'expired', so create_render_job
-- refuses it from that moment. An upload left 'pending' (never completed) for a day is claimed too.
create or replace function public.expire_uploads(p_limit integer default 100)
returns table (upload_id uuid, user_id uuid, r2_key text)
language plpgsql
set search_path = ''
as $$
declare
  v_limit integer := greatest(1, least(coalesce(p_limit, 100), 500));
begin
  with due as (
    select u.id
      from public.uploads u
     where u.source = 'upload'
       and u.expired_at is null
       and u.created_at <= now() - interval '1 day'
       and not exists (select 1 from public.render_jobs j
                        where j.upload_id = u.id and j.status in ('queued', 'running'))
       and (
         u.status = 'pending'
         or greatest(coalesce(u.completed_at, u.created_at), coalesce(u.last_used_at, u.created_at),
                     coalesce((select max(j.created_at) from public.render_jobs j where j.upload_id = u.id), u.created_at))
            + make_interval(days => greatest(
                (select l.retention_days from public.user_plan_limits(u.user_id) l),
                coalesce((select max(pl.retention_days) from public.billing_subscriptions s
                            cross join lateral public.plan_limits(s.plan) pl
                           where s.user_id = u.user_id
                             and coalesce(s.paid_through, s.current_period_end) > now() - interval '30 days'), 0)))
            <= now()
       )
     order by u.created_at
     limit v_limit
     for update of u skip locked
  )
  update public.uploads u
     set expired_at = now(),
         status = 'rejected',
         reject_reason = 'expired'
    from due
   where u.id = due.id;

  return query
    select u.id, u.user_id, u.r2_key
      from public.uploads u
     where u.source = 'upload' and u.expired_at is not null and u.purged_at is null
     order by u.expired_at desc
     limit v_limit;
end $$;

-- Records that the R2 objects of these claimed uploads are gone. Idempotent.
create or replace function public.mark_uploads_purged(p_upload_ids uuid[])
returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  update public.uploads set purged_at = now()
   where id = any (p_upload_ids) and expired_at is not null and purged_at is null;
  get diagnostics v_count = row_count;
  return v_count;
end $$;

revoke all on function public.expired_render_outputs(integer) from public, anon, authenticated;
revoke all on function public.mark_render_outputs_expired(uuid[]) from public, anon, authenticated;
revoke all on function public.expire_uploads(integer) from public, anon, authenticated;
revoke all on function public.mark_uploads_purged(uuid[]) from public, anon, authenticated;
grant execute on function public.expired_render_outputs(integer) to service_role;
grant execute on function public.mark_render_outputs_expired(uuid[]) to service_role;
grant execute on function public.expire_uploads(integer) to service_role;
grant execute on function public.mark_uploads_purged(uuid[]) to service_role;
