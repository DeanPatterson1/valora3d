-- Valora3D render pipeline (Lane D2, 2026-09-28).
--
-- render_jobs gains the RunPod lifecycle (stage/frame progress, outputs, timings, error code, retry count),
-- render_job_private keeps what users must never read (the webhook token hash, operator error detail, the
-- worker's log tail and pin), and finish_render_job() makes the one terminal transition atomic with its
-- refund. Rules from the init migration hold: RLS on, service role only for writes, SECURITY INVOKER.

alter table public.render_jobs
  add column stage            text check (stage is null or char_length(stage) <= 32),
  add column frame            integer not null default 0 check (frame >= 0),
  add column total_frames     integer check (total_frames is null or total_frames >= 0),
  add column runpod_status    text check (runpod_status is null or char_length(runpod_status) <= 32),
  add column error_code       text check (error_code is null or char_length(error_code) <= 64),
  add column retryable        boolean,
  add column outputs          jsonb,
  add column video            jsonb,
  add column timings          jsonb,
  add column warnings         jsonb not null default '[]'::jsonb,
  add column render_seconds   double precision,
  add column gpu_seconds      double precision,
  add column delay_ms         bigint,
  add column execution_ms     bigint,
  -- Resubmissions after a retryable failure (the worker contract: auto-retry once).
  add column attempts         smallint not null default 0 check (attempts between 0 and 5),
  add column refunded_credits integer not null default 0 check (refunded_credits >= 0),
  add column submitted_at     timestamptz,
  add column last_polled_at   timestamptz,
  add column notified_at      timestamptz;

-- The sweeper's scan: live jobs by age.
create index render_jobs_live_idx on public.render_jobs (updated_at)
  where status in ('queued', 'running');
create index render_jobs_project_idx on public.render_jobs (project_id, created_at desc);

create table public.render_job_private (
  job_id             uuid primary key references public.render_jobs (id) on delete cascade,
  -- SHA-256 (hex) of the per-job random token in the webhook URL. The token itself is never stored.
  webhook_token_hash text not null check (webhook_token_hash ~ '^[0-9a-f]{64}$'),
  error_detail       text check (error_detail is null or char_length(error_detail) <= 4000),
  log_tail           jsonb,
  pin                jsonb,
  direct             jsonb,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);
create trigger render_job_private_touch before update on public.render_job_private
  for each row execute function public.touch_updated_at();

alter table public.render_job_private enable row level security;
revoke all on public.render_job_private from anon, authenticated;
grant all on public.render_job_private to service_role;
-- No policies: users (and anon) can never read or write it; the service role bypasses RLS.

-- The one terminal transition of a job attempt. Idempotent on (job, runpod id): only a job still queued or
-- running, on the SAME RunPod attempt, moves; a second webhook, a late poll or an old attempt's report
-- changes nothing. A failure or an early cancel refunds in the same transaction.
-- Returns -1 when nothing moved, else the credits refunded by this call (0 for a success).
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

revoke all on function public.finish_render_job(uuid, text, public.render_job_status, text, text, boolean, jsonb, boolean)
  from public, anon, authenticated;
grant execute on function public.finish_render_job(uuid, text, public.render_job_status, text, text, boolean, jsonb, boolean)
  to service_role;
