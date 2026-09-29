-- Valora3D owner/operator console (admin lane, 2026-09-29).
--
-- Adds what /admin needs, and nothing the rest of the app depends on:
--   * admins                  who may open /admin. A signed-in user can read only their OWN row (so the proxy
--                             can answer "am I an admin?" with the user's session); nobody but the service role
--                             writes it. Seed the owner by hand (below).
--   * admin_audit_log         one append-only row per admin action (who, what, target, why, when). Actions carry a
--                             request id, unique here, so a replayed click is recorded (and applied) once.
--   * billing_webhook_errors  Paddle webhook failures (config / parse / apply). A failed apply rolls back its
--                             billing_events row, so without this table a failing event leaves no trace in the
--                             database. Written best-effort by the webhook route; nothing reads it but /admin.
--   * admin_* functions       the console's aggregate + actions. Service role only, SECURITY INVOKER, and each
--                             re-checks that the acting user is an admin (defence in depth behind the API route).
-- Rules from the init migration hold: RLS on every table, no SECURITY DEFINER, search_path ''.
--
-- Make the owner an admin (Supabase dashboard -> SQL editor, once, after they have signed up):
--   insert into public.admins (user_id, note)
--   select id, 'owner' from auth.users where lower(email) = lower('owner@example.com')
--   on conflict (user_id) do nothing;
-- Remove an admin: delete from public.admins where user_id = '<uuid>';

-- ---------------------------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------------------------

create table public.admins (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  note       text not null default '' check (char_length(note) <= 200),
  created_at timestamptz not null default now()
);

create table public.admin_audit_log (
  id          bigint generated always as identity primary key,
  -- No FK: the history outlives the admin's account.
  admin_id    uuid not null,
  action      text not null check (action in ('credits_adjust', 'render_refund', 'render_retry')),
  target_type text not null check (target_type in ('user', 'render_job')),
  target_id   text not null check (char_length(target_id) between 1 and 64),
  reason      text check (reason is null or char_length(reason) <= 500),
  detail      jsonb not null default '{}'::jsonb,
  -- Idempotency: the same request id is one action, however many times it arrives.
  request_id  text unique check (request_id is null or request_id ~ '^[A-Za-z0-9:_-]{8,128}$'),
  created_at  timestamptz not null default now()
);
create index admin_audit_log_created_idx on public.admin_audit_log (created_at desc);
create index admin_audit_log_target_idx on public.admin_audit_log (target_type, target_id, created_at desc);

create or replace function public.admin_audit_log_block_change() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'admin_audit_log is append-only' using errcode = '42501';
end $$;

create trigger admin_audit_log_append_only
  before update or delete on public.admin_audit_log
  for each row execute function public.admin_audit_log_block_change();

create table public.billing_webhook_errors (
  id          bigint generated always as identity primary key,
  received_at timestamptz not null default now(),
  -- Only recorded after the signature verified, so these are Paddle's, not a stranger's.
  event_id    text check (event_id is null or event_id ~ '^evt_[a-z0-9]+$'),
  event_type  text check (event_type is null or char_length(event_type) <= 64),
  stage       text not null check (stage in ('config', 'parse', 'apply')),
  code        text check (code is null or char_length(code) <= 16),
  message     text check (message is null or char_length(message) <= 500)
);
create index billing_webhook_errors_received_idx on public.billing_webhook_errors (received_at desc);

-- ---------------------------------------------------------------------------------------------
-- Privileges + RLS
-- ---------------------------------------------------------------------------------------------

alter table public.admins                 enable row level security;
alter table public.admin_audit_log        enable row level security;
alter table public.billing_webhook_errors enable row level security;

revoke all on public.admins, public.admin_audit_log, public.billing_webhook_errors from anon, authenticated;
revoke all on sequence public.admin_audit_log_id_seq, public.billing_webhook_errors_id_seq from anon, authenticated;
grant select on public.admins to authenticated;
grant all on public.admins, public.admin_audit_log, public.billing_webhook_errors to service_role;
grant usage, select on sequence public.admin_audit_log_id_seq, public.billing_webhook_errors_id_seq to service_role;

-- A user learns only whether they themselves are an admin.
create policy admins_select_self on public.admins
  for select to authenticated using (user_id = (select auth.uid()));
-- admin_audit_log, billing_webhook_errors: no policies (service role only).

-- ---------------------------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------------------------

create or replace function public.is_admin(p_user_id uuid) returns boolean
language sql stable
set search_path = ''
as $$ select exists (select 1 from public.admins where user_id = p_user_id) $$;

create or replace function public.admin_assert(p_admin_id uuid) returns void
language plpgsql stable
set search_path = ''
as $$
begin
  if p_admin_id is null or not public.is_admin(p_admin_id) then
    raise exception 'not an admin' using errcode = '42501';
  end if;
end $$;

-- A reason is required for every money action: trimmed, 3..500 characters.
create or replace function public.admin_clean_reason(p_reason text) returns text
language plpgsql immutable
set search_path = ''
as $$
declare
  v text := btrim(coalesce(p_reason, ''));
begin
  if char_length(v) < 3 or char_length(v) > 500 then
    raise exception 'a reason of 3 to 500 characters is required' using errcode = '22023';
  end if;
  return v;
end $$;

create or replace function public.admin_check_request_id(p_request_id text) returns void
language plpgsql immutable
set search_path = ''
as $$
begin
  if p_request_id is null or p_request_id !~ '^[A-Za-z0-9:_-]{8,128}$' then
    raise exception 'request id required' using errcode = '22023';
  end if;
end $$;

-- Serialises two arrivals of the same request id (a double click, a retried fetch).
create or replace function public.admin_lock_request(p_request_id text) returns void
language sql
set search_path = ''
as $$ select pg_advisory_xact_lock(hashtextextended('admin-request:' || p_request_id, 0)) $$;

-- ---------------------------------------------------------------------------------------------
-- Actions
-- ---------------------------------------------------------------------------------------------

-- Grant (positive) or deduct (negative) credits. One ledger row, reason 'admin_adjustment', ref
-- 'admin:<request_id>', and one audit row naming the admin, both in this transaction. A replay of the same
-- request id returns the first result and changes nothing; the same id with different details is refused.
-- A deduction may take the balance below zero (like a chargeback): renders are then refused until it recovers.
create or replace function public.admin_adjust_credits(
  p_admin_id   uuid,
  p_user_id    uuid,
  p_amount     integer,
  p_reason     text,
  p_request_id text
) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_reason text;
  v_audit  public.admin_audit_log;
  v_ledger public.credit_ledger;
  v_balance integer;
begin
  perform public.admin_assert(p_admin_id);
  perform public.admin_check_request_id(p_request_id);
  v_reason := public.admin_clean_reason(p_reason);
  if p_amount is null or p_amount = 0 or abs(p_amount) > 100000 then
    raise exception 'amount must be a non-zero whole number up to 100000' using errcode = '22023';
  end if;
  if not exists (select 1 from public.profiles where id = p_user_id) then
    raise exception 'user not found' using errcode = 'P0002';
  end if;

  perform public.admin_lock_request(p_request_id);
  perform public.lock_user_credits(p_user_id);

  select * into v_audit from public.admin_audit_log where request_id = p_request_id;
  if found then
    if v_audit.action <> 'credits_adjust' or v_audit.target_id <> p_user_id::text
       or (v_audit.detail ->> 'amount')::integer <> p_amount then
      raise exception 'request id reused with different details' using errcode = '23505';
    end if;
    return jsonb_build_object('replay', true, 'ledger_id', v_audit.detail -> 'ledger_id',
                              'amount', p_amount, 'balance', public.user_balance(p_user_id));
  end if;

  insert into public.credit_ledger (user_id, amount, reason, ref)
  values (p_user_id, p_amount, 'admin_adjustment', 'admin:' || p_request_id)
  returning * into v_ledger;
  v_balance := public.user_balance(p_user_id);

  insert into public.admin_audit_log (admin_id, action, target_type, target_id, reason, detail, request_id)
  values (p_admin_id, 'credits_adjust', 'user', p_user_id::text, v_reason,
          jsonb_build_object('amount', p_amount, 'ledger_id', v_ledger.id, 'balance_after', v_balance), p_request_id);

  return jsonb_build_object('replay', false, 'ledger_id', v_ledger.id, 'amount', p_amount, 'balance', v_balance);
end $$;

-- Refund a failed or cancelled render through the existing refund_render_job (itself idempotent per job: a
-- job is refunded at most once, whoever asks). Records render_jobs.refunded_credits and one audit row.
-- Returns {"replay", "refunded"}: refunded is 0 when the job had already been refunded.
create or replace function public.admin_refund_render_job(
  p_admin_id   uuid,
  p_job_id     uuid,
  p_reason     text,
  p_request_id text
) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_reason   text;
  v_audit    public.admin_audit_log;
  v_refunded integer;
begin
  perform public.admin_assert(p_admin_id);
  perform public.admin_check_request_id(p_request_id);
  v_reason := public.admin_clean_reason(p_reason);

  perform public.admin_lock_request(p_request_id);
  select * into v_audit from public.admin_audit_log where request_id = p_request_id;
  if found then
    if v_audit.action <> 'render_refund' or v_audit.target_id <> p_job_id::text then
      raise exception 'request id reused with different details' using errcode = '23505';
    end if;
    return jsonb_build_object('replay', true, 'refunded', coalesce((v_audit.detail ->> 'refunded')::integer, 0));
  end if;

  v_refunded := public.refund_render_job(p_job_id);
  if v_refunded > 0 then
    update public.render_jobs set refunded_credits = refunded_credits + v_refunded where id = p_job_id;
  end if;

  insert into public.admin_audit_log (admin_id, action, target_type, target_id, reason, detail, request_id)
  values (p_admin_id, 'render_refund', 'render_job', p_job_id::text, v_reason,
          jsonb_build_object('refunded', v_refunded), p_request_id);

  return jsonb_build_object('replay', false, 'refunded', v_refunded);
end $$;

-- Records an action whose effect happened elsewhere (a retry goes through the render pipeline in the API
-- route). Idempotent on the request id. Returns true when this call wrote the row.
create or replace function public.admin_record_action(
  p_admin_id    uuid,
  p_action      text,
  p_target_type text,
  p_target_id   text,
  p_reason      text,
  p_detail      jsonb,
  p_request_id  text
) returns boolean
language plpgsql
set search_path = ''
as $$
declare
  v_inserted integer;
begin
  perform public.admin_assert(p_admin_id);
  perform public.admin_check_request_id(p_request_id);
  insert into public.admin_audit_log (admin_id, action, target_type, target_id, reason, detail, request_id)
  values (p_admin_id, p_action, p_target_type, p_target_id, nullif(left(btrim(coalesce(p_reason, '')), 500), ''),
          coalesce(p_detail, '{}'::jsonb), p_request_id)
  on conflict (request_id) do nothing;
  get diagnostics v_inserted = row_count;
  return v_inserted > 0;
end $$;

-- Best-effort log of a failed Paddle webhook (the route ignores any error from this call). Keeps 90 days.
create or replace function public.log_billing_webhook_error(
  p_stage      text,
  p_event_id   text,
  p_event_type text,
  p_code       text,
  p_message    text
) returns void
language plpgsql
set search_path = ''
as $$
begin
  insert into public.billing_webhook_errors (stage, event_id, event_type, code, message)
  values (
    p_stage,
    case when p_event_id ~ '^evt_[a-z0-9]+$' then p_event_id end,
    left(p_event_type, 64),
    left(p_code, 16),
    left(p_message, 500)
  );
  delete from public.billing_webhook_errors where received_at < now() - interval '90 days';
end $$;

-- ---------------------------------------------------------------------------------------------
-- Overview
-- ---------------------------------------------------------------------------------------------

-- Credits, renders and revenue since p_since.
create or replace function public.admin_window_stats(p_since timestamptz) returns jsonb
language sql stable
set search_path = ''
as $$
  select jsonb_build_object(
    'since', p_since,
    'credits', (
      select jsonb_build_object(
        'granted', coalesce(sum(amount) filter (where reason in ('signup_grant', 'plan_grant', 'pack_purchase')
                                                   or (reason = 'admin_adjustment' and amount > 0)), 0),
        'spent', coalesce(-sum(amount) filter (where reason in ('scene_generation', 'prompt_edit', 'preview_render',
                                                                'render_preview', 'render_final')), 0),
        'refunded', coalesce(sum(amount) filter (where reason = 'render_refund'), 0),
        'reversed', coalesce(-sum(amount) filter (where reason = 'billing_reversal'), 0),
        'admin_deducted', coalesce(-sum(amount) filter (where reason = 'admin_adjustment' and amount < 0), 0),
        'by_reason', coalesce((
          select jsonb_object_agg(r.reason, r.total)
          from (select reason, sum(amount)::bigint as total from public.credit_ledger
                 where created_at >= p_since group by reason) r), '{}'::jsonb))
      from public.credit_ledger where created_at >= p_since),
    'renders', (
      select jsonb_build_object(
        'total', count(*),
        'by_status', coalesce((
          select jsonb_object_agg(s.status, s.n)
          from (select status::text as status, count(*) as n from public.render_jobs
                 where created_at >= p_since group by status) s), '{}'::jsonb),
        'finished', count(*) filter (where status in ('succeeded', 'failed')),
        'failure_rate', case when count(*) filter (where status in ('succeeded', 'failed')) = 0 then null
                             else round((count(*) filter (where status = 'failed'))::numeric
                                        / count(*) filter (where status in ('succeeded', 'failed')), 4) end,
        'avg_render_seconds', round(avg(render_seconds) filter (where status = 'succeeded')::numeric, 1),
        'avg_wall_seconds', round(avg(extract(epoch from finished_at - created_at))
                                  filter (where status = 'succeeded')::numeric, 1),
        'gpu_seconds', round(coalesce(sum(gpu_seconds), 0)::numeric, 1),
        'execution_seconds', round(coalesce(sum(execution_ms), 0)::numeric / 1000, 1))
      from public.render_jobs where created_at >= p_since),
    'revenue', coalesce((
      select jsonb_agg(jsonb_build_object('currency', t.currency, 'gross_minor', t.gross, 'transactions', t.n,
                                          'credits_reversed', t.reversed) order by t.gross desc)
      from (select coalesce(currency_code, '?') as currency, sum(total_minor)::bigint as gross, count(*) as n,
                   sum(credits_reversed)::bigint as reversed
              from public.billing_transactions where created_at >= p_since
             group by coalesce(currency_code, '?')) t), '[]'::jsonb),
    'adjustments', (select count(*) from public.billing_adjustments where created_at >= p_since),
    'webhook_errors', (select count(*) from public.billing_webhook_errors where received_at >= p_since)
  )
$$;

create or replace function public.admin_overview() returns jsonb
language sql stable
set search_path = ''
as $$
  select jsonb_build_object(
    'generated_at', now(),
    'signups', (
      select jsonb_build_object(
        'today', count(*) filter (where created_at >= date_trunc('day', now() at time zone 'utc') at time zone 'utc'),
        'd7', count(*) filter (where created_at >= now() - interval '7 days'),
        'd30', count(*) filter (where created_at >= now() - interval '30 days'),
        'total', count(*))
      from public.profiles),
    -- profiles.plan is the display copy kept in sync by billing and sync_expired_plans().
    'plans', coalesce((
      select jsonb_object_agg(p.plan, p.n)
      from (select plan::text as plan, count(*) as n from public.profiles group by plan) p), '{}'::jsonb),
    -- Users with a live paid subscription (what user_plan() counts as paying), per plan.
    'paying', coalesce((
      select jsonb_object_agg(s.plan, s.n)
      from (select plan::text as plan, count(distinct user_id) as n from public.billing_subscriptions
             where (status in ('active', 'trialing') or paid_through > now())
               and (revoked_through is null or revoked_through <= now())
             group by plan) s), '{}'::jsonb),
    'live_renders', (select count(*) from public.render_jobs where status in ('queued', 'running')),
    'windows', jsonb_build_object(
      'd1', public.admin_window_stats(now() - interval '1 day'),
      'd7', public.admin_window_stats(now() - interval '7 days'),
      'd30', public.admin_window_stats(now() - interval '30 days'))
  )
$$;

-- Users by email fragment (or exact id), newest first; an empty query lists the newest users.
create or replace function public.admin_find_users(p_query text, p_limit integer default 25)
returns table (id uuid, email text, name text, plan public.plan_tier, created_at timestamptz, balance integer)
language plpgsql stable
set search_path = ''
as $$
declare
  v_q text := btrim(coalesce(p_query, ''));
  v_limit integer := least(greatest(coalesce(p_limit, 25), 1), 100);
  v_pattern text;
begin
  if v_q ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    return query
      select p.id, p.email, p.name, p.plan, p.created_at, public.user_balance(p.id)
      from public.profiles p where p.id = v_q::uuid;
    return;
  end if;
  -- Match the text literally: escape LIKE's wildcards and its escape character.
  v_pattern := '%' || replace(replace(replace(lower(left(v_q, 200)), '\', '\\'), '%', '\%'), '_', '\_') || '%';
  return query
    select p.id, p.email, p.name, p.plan, p.created_at, public.user_balance(p.id)
    from public.profiles p
    where v_q = '' or lower(p.email) like v_pattern escape '\'
    order by p.created_at desc
    limit v_limit;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Function privileges: service role only.
-- ---------------------------------------------------------------------------------------------

revoke all on function public.is_admin(uuid) from public, anon, authenticated;
revoke all on function public.admin_assert(uuid) from public, anon, authenticated;
revoke all on function public.admin_clean_reason(text) from public, anon, authenticated;
revoke all on function public.admin_check_request_id(text) from public, anon, authenticated;
revoke all on function public.admin_lock_request(text) from public, anon, authenticated;
revoke all on function public.admin_adjust_credits(uuid, uuid, integer, text, text) from public, anon, authenticated;
revoke all on function public.admin_refund_render_job(uuid, uuid, text, text) from public, anon, authenticated;
revoke all on function public.admin_record_action(uuid, text, text, text, text, jsonb, text) from public, anon, authenticated;
revoke all on function public.log_billing_webhook_error(text, text, text, text, text) from public, anon, authenticated;
revoke all on function public.admin_window_stats(timestamptz) from public, anon, authenticated;
revoke all on function public.admin_overview() from public, anon, authenticated;
revoke all on function public.admin_find_users(text, integer) from public, anon, authenticated;
revoke all on function public.admin_audit_log_block_change() from public, anon, authenticated;

grant execute on function public.is_admin(uuid) to service_role;
grant execute on function public.admin_assert(uuid) to service_role;
grant execute on function public.admin_clean_reason(text) to service_role;
grant execute on function public.admin_check_request_id(text) to service_role;
grant execute on function public.admin_lock_request(text) to service_role;
grant execute on function public.admin_adjust_credits(uuid, uuid, integer, text, text) to service_role;
grant execute on function public.admin_refund_render_job(uuid, uuid, text, text) to service_role;
grant execute on function public.admin_record_action(uuid, text, text, text, text, jsonb, text) to service_role;
grant execute on function public.log_billing_webhook_error(text, text, text, text, text) to service_role;
grant execute on function public.admin_window_stats(timestamptz) to service_role;
grant execute on function public.admin_overview() to service_role;
grant execute on function public.admin_find_users(text, integer) to service_role;
