-- Valora3D analytics, feature flags, error monitoring and owner alerts (analytics lane, 2026-09-30).
--
-- Adds, all first-party and cookieless (the one cookie is the first-touch attribution cookie, set by proxy.ts):
--   * product_events      append-only product events. Server events come from the source-of-truth tables through
--                         triggers (signup confirmed, first project, uploads, scene versions, renders, shares, billing);
--                         browser events (landing/pricing views, CTA clicks, signup start, help search) arrive through
--                         POST /api/events -> record_client_events(). No PII: a user id OR a random per-tab session id,
--                         a route template, an allowlisted event name and small allowlisted props.
--   * profiles.signup_source, billing_transactions.source   first-touch attribution (utm_*/ref/referrer host).
--   * render_jobs cost columns   cost_usd_estimate + director token counts, written once at finish.
--   * feature_flags       kill switches and numeric settings, edited from /admin (audited in admin_audit_log).
--                         create_render_job enforces renders_enabled / finals_enabled / global_max_active_renders /
--                         daily_gpu_budget_seconds through a BEFORE INSERT trigger on render_jobs (it runs inside
--                         create_render_job's transaction, after the plan and credit checks); signups_enabled is
--                         enforced on auth.users.
--   * client_errors       grouped client error reports (release, route template, error name, digest), 30 days.
--   * owner_alert_state   rate limit for owner alert mails (one per kind per hour; the digest once a day).
--   * admin_growth(), admin_client_errors(), ops_alert_signals(), ops_daily_digest()   service-role reads.
-- Rules from the init migration hold: RLS on every table, no SECURITY DEFINER, search_path '', service role only for
-- functions. Two trigger paths run as other roles and are granted exactly one event each (see "Grants").

-- ---------------------------------------------------------------------------------------------
-- Product events
-- ---------------------------------------------------------------------------------------------

create or replace function public.product_event_names() returns text[]
language sql immutable
set search_path = ''
as $$ select array[
  -- browser (POST /api/events; mirrors CLIENT_EVENTS in lib/analytics/events.ts)
  'landing_view', 'pricing_view', 'cta_click', 'signup_start', 'help_search', 'experiment_exposure',
  -- server (triggers and API routes; mirrors SERVER_EVENTS)
  'signup_complete', 'first_project', 'upload_start', 'upload_ready', 'upload_rejected',
  'scene_generated', 'scene_saved', 'render_requested', 'render_succeeded', 'render_failed',
  'checkout_open', 'checkout_complete', 'plan_canceled', 'share_created', 'share_view', 'share_signup'
]::text[] $$;

create or replace function public.client_event_names() returns text[]
language sql immutable
set search_path = ''
as $$ select array['landing_view', 'pricing_view', 'cta_click', 'signup_start', 'help_search', 'experiment_exposure']::text[] $$;

create table public.product_events (
  id         bigint generated always as identity primary key,
  event      text not null check (event = any (public.product_event_names())),
  -- Kept (as null) when the account is deleted: the counts stay, the person is gone.
  user_id    uuid references auth.users (id) on delete set null,
  -- A random id the browser keeps in sessionStorage (per tab, never a cookie). Null for server events.
  session_id text check (session_id is null or session_id ~ '^[A-Za-z0-9_-]{16,64}$'),
  -- A route template (/projects/[id]), never a query string.
  path       text check (path is null or (char_length(path) <= 120 and path ~ '^/[A-Za-z0-9/_.\[\]-]*$')),
  props      jsonb not null default '{}'::jsonb
             check (jsonb_typeof(props) = 'object' and octet_length(props::text) <= 512),
  source     text not null default 'server' check (source in ('client', 'server')),
  created_at timestamptz not null default now()
);
create index product_events_created_idx on public.product_events (created_at desc);
create index product_events_event_idx on public.product_events (event, created_at desc);
create index product_events_user_idx on public.product_events (user_id, created_at) where user_id is not null;
create index product_events_session_idx on public.product_events (session_id, created_at) where session_id is not null;
-- One first_project per account, so the one event users can cause through RLS (their first project) cannot be spammed.
create unique index product_events_first_project_once on public.product_events (user_id) where event = 'first_project';
create unique index product_events_signup_once on public.product_events (user_id) where event = 'signup_complete';

-- Append-only: rows are never edited. The one allowed update is the FK setting user_id to null when an account is
-- deleted. Old rows are pruned by prune_ops_data() (the cron sweep).
create or replace function public.product_events_block_update() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.user_id is null and old.user_id is not null
     and (new.id, new.event, new.session_id, new.path, new.props, new.source, new.created_at)
         is not distinct from (old.id, old.event, old.session_id, old.path, old.props, old.source, old.created_at) then
    return new;
  end if;
  raise exception 'product_events is append-only' using errcode = '42501';
end $$;

create trigger product_events_append_only
  before update on public.product_events
  for each row execute function public.product_events_block_update();

-- A server-side event from a trigger or a route. Never fails its caller: an analytics row is not worth a render.
create or replace function public.emit_product_event(p_event text, p_user_id uuid, p_props jsonb default '{}'::jsonb)
returns void
language plpgsql
set search_path = ''
as $$
begin
  insert into public.product_events (event, user_id, props, source)
  values (p_event, p_user_id, coalesce(p_props, '{}'::jsonb), 'server');
exception when others then
  null;
end $$;

-- A route's own event (checkout_open, share_view from the page...). Same as above, plus the route template.
create or replace function public.record_product_event(p_event text, p_user_id uuid, p_props jsonb, p_path text)
returns boolean
language plpgsql
set search_path = ''
as $$
begin
  -- experiment_exposure may come from either side (the server helper logs the variant it served).
  if p_event is null or not (p_event = any (public.product_event_names()))
     or (p_event = any (public.client_event_names()) and p_event <> 'experiment_exposure') then
    raise exception 'unknown server event' using errcode = '22023';
  end if;
  insert into public.product_events (event, user_id, props, path, source)
  values (p_event, p_user_id, coalesce(p_props, '{}'::jsonb), p_path, 'server');
  return true;
end $$;

-- Hourly ceilings for browser events, per session and per signed-in user (the route also rate-limits per IP).
create or replace function public.client_events_hourly_cap() returns integer
language sql immutable set search_path = '' as $$ select 300 $$;

-- A batch from POST /api/events, already validated by the route (lib/analytics/events.ts). Only browser event
-- names are accepted here; a batch past the hourly ceiling is dropped whole. Returns the rows written.
create or replace function public.record_client_events(p_session_id text, p_user_id uuid, p_events jsonb)
returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_n integer;
  v_recent integer;
begin
  if p_session_id is null or p_session_id !~ '^[A-Za-z0-9_-]{16,64}$' then
    raise exception 'bad session id' using errcode = '22023';
  end if;
  if jsonb_typeof(p_events) <> 'array' or jsonb_array_length(p_events) = 0 then
    return 0;
  end if;
  if jsonb_array_length(p_events) > 25 then
    raise exception 'too many events' using errcode = '22023';
  end if;
  if exists (select 1 from jsonb_array_elements(p_events) e
              where not ((e ->> 'event') = any (public.client_event_names()))) then
    raise exception 'not a browser event' using errcode = '22023';
  end if;

  select count(*) into v_recent from public.product_events
   where created_at > now() - interval '1 hour'
     and (session_id = p_session_id or (p_user_id is not null and user_id = p_user_id and source = 'client'));
  if v_recent + jsonb_array_length(p_events) > public.client_events_hourly_cap() then
    return 0;
  end if;

  insert into public.product_events (event, user_id, session_id, path, props, source)
  select e ->> 'event', p_user_id, p_session_id, nullif(e ->> 'path', ''),
         coalesce(case when jsonb_typeof(e -> 'props') = 'object' then e -> 'props' end, '{}'::jsonb), 'client'
    from jsonb_array_elements(p_events) e;
  get diagnostics v_n = row_count;
  return v_n;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Attribution
-- ---------------------------------------------------------------------------------------------

-- First touch: {source, medium, campaign, ref, landing, referrer, at}. Short, sanitised strings (lib/analytics/attribution.ts).
create or replace function public.attribution_ok(p jsonb) returns boolean
language sql immutable
set search_path = ''
as $$
  select p is null or (jsonb_typeof(p) = 'object' and octet_length(p::text) <= 600
    and not exists (select 1 from jsonb_each(p) kv
                     where kv.key not in ('source', 'medium', 'campaign', 'content', 'term', 'ref', 'landing', 'referrer', 'at')
                        or jsonb_typeof(kv.value) <> 'string'
                        or char_length(kv.value #>> '{}') > 120))
$$;

alter table public.profiles
  add column signup_source jsonb check (public.attribution_ok(signup_source));
alter table public.billing_transactions
  add column source jsonb check (public.attribution_ok(source));

-- Called by the auth callback / confirm routes (and the events route) with the first-touch cookie. Sets the source
-- once, and only for an account made in the last day (an old account is not re-attributed to a new campaign).
-- A signup that came from a share page link (ref share_<slug>) also records share_signup. True when it wrote.
create or replace function public.record_signup_source(p_user_id uuid, p_source jsonb) returns boolean
language plpgsql
set search_path = ''
as $$
declare
  v_updated integer;
begin
  if p_source is null or not public.attribution_ok(p_source) or p_source = '{}'::jsonb then
    return false;
  end if;
  update public.profiles set signup_source = p_source
   where id = p_user_id and signup_source is null and created_at > now() - interval '1 day';
  get diagnostics v_updated = row_count;
  if v_updated > 0 and coalesce(p_source ->> 'ref', '') like 'share\_%' then
    perform public.emit_product_event('share_signup', p_user_id, '{}'::jsonb);
  end if;
  return v_updated > 0;
end $$;

-- A transaction's source: what checkout sent (custom data), else the buyer's signup source.
create or replace function public.billing_transactions_fill_source() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.source is null and new.user_id is not null then
    select p.signup_source into new.source from public.profiles p where p.id = new.user_id;
  end if;
  return new;
end $$;

create trigger billing_transactions_source
  before insert on public.billing_transactions
  for each row execute function public.billing_transactions_fill_source();

-- The webhook, after billing_apply_event: the source that rode along in checkout custom data wins.
create or replace function public.billing_set_transaction_source(p_transaction_id text, p_source jsonb) returns boolean
language plpgsql
set search_path = ''
as $$
declare
  v_updated integer;
begin
  if p_source is null or not public.attribution_ok(p_source) or p_source = '{}'::jsonb then
    return false;
  end if;
  update public.billing_transactions set source = p_source where id = p_transaction_id;
  get diagnostics v_updated = row_count;
  return v_updated > 0;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Server events from the source-of-truth tables
-- ---------------------------------------------------------------------------------------------

-- auth.users (runs as supabase_auth_admin): signup_complete once the email is confirmed (or at once for OAuth).
create or replace function public.product_event_signup_confirmed() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.email_confirmed_at is not null
     and (tg_op = 'INSERT' or old.email_confirmed_at is null) then
    begin
      insert into public.product_events (event, user_id, source) values ('signup_complete', new.id, 'server')
      on conflict do nothing;
    exception when others then
      null;
    end;
  end if;
  return new;
end $$;

create trigger product_event_signup_insert
  after insert on auth.users
  for each row execute function public.product_event_signup_confirmed();
create trigger product_event_signup_confirm
  after update of email_confirmed_at on auth.users
  for each row execute function public.product_event_signup_confirmed();

-- projects (inserted by the user under RLS): first_project, once per account (unique index above).
create or replace function public.product_event_first_project() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  begin
    insert into public.product_events (event, user_id, source) values ('first_project', new.user_id, 'server')
    on conflict do nothing;
  exception when others then
    null;
  end;
  return new;
end $$;

create trigger product_event_first_project
  after insert on public.projects
  for each row execute function public.product_event_first_project();

-- uploads (service role): start, ready, rejected with a coarse reason. Retention expiry is not a rejection.
create or replace function public.upload_reject_code(p_reason text) returns text
language sql immutable
set search_path = ''
as $$
  select case
    when p_reason is null then 'other'
    when p_reason ilike '%empty%' then 'empty'
    when p_reason ilike '%larger than%' then 'too_large'
    when p_reason ilike '%does not match%' then 'size_mismatch'
    when p_reason ilike '%glb%' or p_reason ilike '%gltf%' or p_reason ilike '%header%' then 'not_glb'
    else 'other'
  end
$$;

create or replace function public.product_event_upload() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.source <> 'upload' then
    return new;
  end if;
  if tg_op = 'INSERT' then
    perform public.emit_product_event('upload_start', new.user_id, '{}'::jsonb);
  elsif old.status = 'pending' and new.status = 'ready' then
    perform public.emit_product_event('upload_ready', new.user_id, '{}'::jsonb);
  elsif old.status = 'pending' and new.status = 'rejected' and coalesce(new.reject_reason, '') <> 'expired' then
    perform public.emit_product_event('upload_rejected', new.user_id,
      jsonb_build_object('reason', public.upload_reject_code(new.reject_reason)));
  end if;
  return new;
end $$;

create trigger product_event_upload_insert
  after insert on public.uploads
  for each row execute function public.product_event_upload();
create trigger product_event_upload_status
  after update of status on public.uploads
  for each row execute function public.product_event_upload();

-- scene_versions (save_scene_version, service role): the first version is the generation, later ones are saves.
create or replace function public.product_event_scene_version() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  perform public.emit_product_event(case when new.index = 0 then 'scene_generated' else 'scene_saved' end, new.user_id, '{}'::jsonb);
  return new;
end $$;

create trigger product_event_scene_version
  after insert on public.scene_versions
  for each row execute function public.product_event_scene_version();

-- render_jobs (service role): requested, then one terminal event with the tier (and the error code on failure).
create or replace function public.product_event_render() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    perform public.emit_product_event('render_requested', new.user_id, jsonb_build_object('tier', new.kind::text));
  elsif new.status is distinct from old.status then
    if new.status = 'succeeded' then
      perform public.emit_product_event('render_succeeded', new.user_id, jsonb_build_object('tier', new.kind::text));
    elsif new.status = 'failed' then
      perform public.emit_product_event('render_failed', new.user_id,
        jsonb_build_object('tier', new.kind::text, 'code', left(coalesce(new.error_code, 'UNKNOWN'), 40)));
    end if;
  end if;
  return new;
end $$;

create trigger product_event_render_insert
  after insert on public.render_jobs
  for each row execute function public.product_event_render();
create trigger product_event_render_status
  after update of status on public.render_jobs
  for each row execute function public.product_event_render();

-- render_shares (service role): created, and one share_view per counted page view.
create or replace function public.product_event_share() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    perform public.emit_product_event('share_created', new.user_id, '{}'::jsonb);
  elsif new.view_count > old.view_count then
    perform public.emit_product_event('share_view', null, '{}'::jsonb);
  end if;
  return new;
end $$;

create trigger product_event_share_insert
  after insert on public.render_shares
  for each row execute function public.product_event_share();
create trigger product_event_share_view
  after update of view_count on public.render_shares
  for each row execute function public.product_event_share();

-- billing_transactions (webhook, service role): checkout_complete for a pack, a plan's first paid period and a plan
-- change. A renewal of the same plan is not a checkout.
create or replace function public.product_event_transaction() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_prev public.plan_tier;
  v_has_prev boolean;
begin
  if new.kind = 'pack' then
    perform public.emit_product_event('checkout_complete', new.user_id,
      jsonb_build_object('item', 'pack:' || new.credits_granted::text));
    return new;
  end if;
  select true, t.plan into v_has_prev, v_prev from public.billing_transactions t
   where t.subscription_id = new.subscription_id and t.id <> new.id
   order by t.created_at desc limit 1;
  if v_has_prev is null or v_prev is distinct from new.plan then
    perform public.emit_product_event('checkout_complete', new.user_id,
      jsonb_build_object('item', 'plan:' || coalesce(new.plan::text, 'unknown')));
  end if;
  return new;
end $$;

create trigger product_event_transaction
  after insert on public.billing_transactions
  for each row execute function public.product_event_transaction();

-- billing_subscriptions (webhook, service role): plan_canceled when a subscription turns canceled.
create or replace function public.product_event_subscription() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.status = 'canceled' and (tg_op = 'INSERT' or old.status is distinct from 'canceled') then
    perform public.emit_product_event('plan_canceled', new.user_id, jsonb_build_object('plan', new.plan::text));
  end if;
  return new;
end $$;

create trigger product_event_subscription_insert
  after insert on public.billing_subscriptions
  for each row execute function public.product_event_subscription();
create trigger product_event_subscription_status
  after update of status on public.billing_subscriptions
  for each row execute function public.product_event_subscription();

-- ---------------------------------------------------------------------------------------------
-- Per-job cost
-- ---------------------------------------------------------------------------------------------

alter table public.render_jobs
  -- gpu_seconds x GPU_USD_PER_SECOND (+ director tokens x their rates), written once when the job finishes.
  add column cost_usd_estimate      numeric(12, 4) check (cost_usd_estimate is null or cost_usd_estimate >= 0),
  add column director_input_tokens  integer check (director_input_tokens is null or director_input_tokens >= 0),
  add column director_output_tokens integer check (director_output_tokens is null or director_output_tokens >= 0);

-- Idempotent: only a job without a cost yet is written (a duplicate webhook changes nothing).
create or replace function public.set_render_job_cost(
  p_job_id        uuid,
  p_cost_usd      numeric,
  p_input_tokens  integer,
  p_output_tokens integer
) returns boolean
language plpgsql
set search_path = ''
as $$
declare
  v_updated integer;
begin
  if p_cost_usd is not null and (p_cost_usd < 0 or p_cost_usd > 100000) then
    raise exception 'cost out of range' using errcode = '22023';
  end if;
  update public.render_jobs
     set cost_usd_estimate = round(p_cost_usd, 4),
         director_input_tokens = case when p_input_tokens >= 0 then p_input_tokens end,
         director_output_tokens = case when p_output_tokens >= 0 then p_output_tokens end
   where id = p_job_id and cost_usd_estimate is null and status in ('succeeded', 'failed', 'cancelled');
  get diagnostics v_updated = row_count;
  return v_updated > 0;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Feature flags, kill switches and numeric settings
-- ---------------------------------------------------------------------------------------------

create table public.feature_flags (
  key             text primary key check (key ~ '^[a-z][a-z0-9_]{1,47}$'),
  description     text not null default '' check (char_length(description) <= 300),
  -- 'flag': on/off with a rollout; 'setting': a number (null = no limit).
  kind            text not null default 'flag' check (kind in ('flag', 'setting')),
  enabled         boolean not null default true,
  rollout_percent smallint not null default 100 check (rollout_percent between 0 and 100),
  -- On for these accounts while a rollout is below 100%.
  allowlist       uuid[] not null default '{}' check (cardinality(allowlist) <= 200),
  value           numeric check (value is null or value >= 0),
  updated_by      uuid,
  updated_at      timestamptz not null default now()
);

insert into public.feature_flags (key, kind, description) values
  ('renders_enabled',  'flag', 'Kill switch: new renders (previews and finals). Off refuses every new render.'),
  ('finals_enabled',   'flag', 'Kill switch: new 1080p final renders only.'),
  ('signups_enabled',  'flag', 'Kill switch: new accounts (email and Google).'),
  ('sharing_enabled',  'flag', 'Kill switch: new share links, and the public share pages.'),
  ('checkout_enabled', 'flag', 'Kill switch: opening a new checkout.');
insert into public.feature_flags (key, kind, value, description) values
  ('global_max_active_renders', 'setting', null, 'Most renders queued or running at once across all users. Empty = no cap.'),
  ('daily_gpu_budget_seconds', 'setting', null, 'GPU seconds per UTC day (finished + in flight). Past it, new renders get a friendly "high demand" answer. Empty = no budget.'),
  ('gpu_seconds_estimate_preview', 'setting', 720, 'GPU seconds counted for a preview still in flight (budget guard).'),
  ('gpu_seconds_estimate_final', 'setting', 10800, 'GPU seconds counted for a final still in flight (budget guard).');

-- A kill switch as the database sees it: global only (the rollout is for the app's own flag() helper). A missing
-- row is on.
create or replace function public.flag_enabled(p_key text) returns boolean
language sql stable
set search_path = ''
as $$ select coalesce((select enabled from public.feature_flags where key = p_key), true) $$;

create or replace function public.setting_value(p_key text) returns numeric
language sql stable
set search_path = ''
as $$ select value from public.feature_flags where key = p_key and kind = 'setting' $$;

-- GPU seconds used today (UTC): measured where known, else RunPod's billed execution, else the per-tier estimate
-- for a job still in flight.
create or replace function public.gpu_seconds_today() returns numeric
language sql stable
set search_path = ''
as $$
  select round(coalesce(sum(case
      when j.gpu_seconds is not null then j.gpu_seconds::numeric
      when j.execution_ms is not null then j.execution_ms::numeric / 1000
      when j.status in ('queued', 'running') then coalesce(public.setting_value(
             case j.kind when 'final' then 'gpu_seconds_estimate_final' else 'gpu_seconds_estimate_preview' end), 0)
      else 0 end), 0), 1)
  from public.render_jobs j
  where j.created_at >= date_trunc('day', now() at time zone 'utc') at time zone 'utc'
$$;

-- Runs inside create_render_job's INSERT (after its plan, cap and credit checks), so every render the site starts
-- passes it: the kill switches, the global concurrency cap and the daily GPU budget.
--   'renders_paused' / 'finals_paused'   (P0001) a kill switch is off
--   'high_demand: capacity|budget'       (P0001) the global cap or today's budget is reached
create or replace function public.render_jobs_capacity_guard() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_cap numeric := public.setting_value('global_max_active_renders');
  v_budget numeric := public.setting_value('daily_gpu_budget_seconds');
begin
  if not public.flag_enabled('renders_enabled') then
    raise exception 'renders_paused' using errcode = 'P0001';
  end if;
  if new.kind = 'final' and not public.flag_enabled('finals_enabled') then
    raise exception 'finals_paused' using errcode = 'P0001';
  end if;
  if v_cap is not null or v_budget is not null then
    -- One render creation at a time while a global limit is set, so two users cannot both take the last slot.
    perform pg_advisory_xact_lock(hashtextextended('valora3d:render-capacity', 0));
    if v_cap is not null and (select count(*) from public.render_jobs where status in ('queued', 'running')) >= v_cap then
      raise exception 'high_demand: capacity' using errcode = 'P0001';
    end if;
    if v_budget is not null and public.gpu_seconds_today() >= v_budget then
      raise exception 'high_demand: budget' using errcode = 'P0001';
    end if;
  end if;
  return new;
end $$;

create trigger render_jobs_capacity_guard
  before insert on public.render_jobs
  for each row execute function public.render_jobs_capacity_guard();

-- auth.users (runs as supabase_auth_admin): no new accounts while signups_enabled is off.
create or replace function public.signups_guard() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not public.flag_enabled('signups_enabled') then
    raise exception 'signups_paused' using errcode = 'P0001';
  end if;
  return new;
end $$;

create trigger signups_guard
  before insert on auth.users
  for each row execute function public.signups_guard();

-- The admin console's edit, audited. Keys are fixed by migrations (no creation from the console). A replayed request
-- id returns the first result.
alter table public.admin_audit_log drop constraint admin_audit_log_action_check;
alter table public.admin_audit_log add constraint admin_audit_log_action_check
  check (action in ('credits_adjust', 'render_refund', 'render_retry', 'flag_update'));
alter table public.admin_audit_log drop constraint admin_audit_log_target_type_check;
alter table public.admin_audit_log add constraint admin_audit_log_target_type_check
  check (target_type in ('user', 'render_job', 'feature_flag'));

create or replace function public.admin_set_flag(
  p_admin_id   uuid,
  p_key        text,
  p_enabled    boolean,
  p_rollout    integer,
  p_allowlist  uuid[],
  p_value      numeric,
  p_reason     text,
  p_request_id text
) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_reason text;
  v_before public.feature_flags;
  v_after  public.feature_flags;
  v_audit  public.admin_audit_log;
begin
  perform public.admin_assert(p_admin_id);
  perform public.admin_check_request_id(p_request_id);
  v_reason := public.admin_clean_reason(p_reason);
  if p_rollout is not null and (p_rollout < 0 or p_rollout > 100) then
    raise exception 'rollout must be 0 to 100' using errcode = '22023';
  end if;
  if p_allowlist is not null and cardinality(p_allowlist) > 200 then
    raise exception 'at most 200 accounts on an allowlist' using errcode = '22023';
  end if;
  if p_value is not null and (p_value < 0 or p_value > 1000000000) then
    raise exception 'value must be 0 or more' using errcode = '22023';
  end if;

  perform public.admin_lock_request(p_request_id);
  select * into v_audit from public.admin_audit_log where request_id = p_request_id;
  if found then
    if v_audit.action <> 'flag_update' or v_audit.target_id <> p_key then
      raise exception 'request id reused with different details' using errcode = '23505';
    end if;
    return jsonb_build_object('replay', true, 'flag', v_audit.detail -> 'after');
  end if;

  select * into v_before from public.feature_flags where key = p_key for update;
  if not found then
    raise exception 'flag not found' using errcode = 'P0002';
  end if;

  update public.feature_flags set
    enabled         = coalesce(p_enabled, enabled),
    rollout_percent = coalesce(p_rollout, rollout_percent),
    allowlist       = coalesce(p_allowlist, allowlist),
    -- A setting's value may be cleared (null = no limit); a flag has none.
    value           = case when kind = 'setting' then p_value else null end,
    updated_by      = p_admin_id,
    updated_at      = now()
  where key = p_key
  returning * into v_after;

  insert into public.admin_audit_log (admin_id, action, target_type, target_id, reason, detail, request_id)
  values (p_admin_id, 'flag_update', 'feature_flag', p_key, v_reason,
          jsonb_build_object(
            'before', jsonb_build_object('enabled', v_before.enabled, 'rollout_percent', v_before.rollout_percent,
                                         'allowlist', to_jsonb(v_before.allowlist), 'value', v_before.value),
            'after', jsonb_build_object('enabled', v_after.enabled, 'rollout_percent', v_after.rollout_percent,
                                        'allowlist', to_jsonb(v_after.allowlist), 'value', v_after.value)),
          p_request_id);

  return jsonb_build_object('replay', false, 'flag', to_jsonb(v_after) - 'updated_by');
end $$;

-- ---------------------------------------------------------------------------------------------
-- Client errors
-- ---------------------------------------------------------------------------------------------

create table public.client_errors (
  id         bigint generated always as identity primary key,
  -- Build id (git short hash) the page was built from.
  release    text not null check (release ~ '^[A-Za-z0-9._-]{1,40}$'),
  -- Route template, never a URL with ids or a query.
  path       text not null check (char_length(path) <= 120 and path ~ '^/[A-Za-z0-9/_.\[\]-]*$'),
  -- Error class name (TypeError, ChunkLoadError...), never the message.
  name       text not null check (name ~ '^[A-Za-z][A-Za-z0-9_]{0,59}$'),
  -- Next's error digest or a fixed code.
  code       text check (code is null or code ~ '^[A-Za-z0-9_:-]{1,40}$'),
  kind       text not null check (kind in ('global', 'segment', 'window', 'promise')),
  ua_family  text not null check (ua_family ~ '^[a-z_]{1,24}$'),
  created_at timestamptz not null default now()
);
create index client_errors_created_idx on public.client_errors (created_at desc);

-- Global flood ceiling on top of the route's per-IP limit: past it, reports are dropped for the hour.
create or replace function public.client_errors_hourly_cap() returns integer
language sql immutable set search_path = '' as $$ select 2000 $$;

create or replace function public.record_client_error(
  p_release text, p_path text, p_name text, p_code text, p_kind text, p_ua_family text
) returns boolean
language plpgsql
set search_path = ''
as $$
begin
  if (select count(*) from public.client_errors where created_at > now() - interval '1 hour') >= public.client_errors_hourly_cap() then
    return false;
  end if;
  insert into public.client_errors (release, path, name, code, kind, ua_family)
  values (p_release, p_path, p_name, p_code, p_kind, p_ua_family);
  return true;
end $$;

-- Grouped by (release, path, name) for /admin -> Errors.
create or replace function public.admin_client_errors(p_since timestamptz) returns jsonb
language sql stable
set search_path = ''
as $$
  select coalesce(jsonb_agg(g order by g.count desc, g.last_seen desc), '[]'::jsonb)
  from (
    select release, path, name, count(*)::integer as count, max(created_at) as last_seen, min(created_at) as first_seen,
           (array_agg(distinct kind))[1:4] as kinds,
           (array_agg(distinct code) filter (where code is not null))[1:5] as codes,
           (array_agg(distinct ua_family))[1:6] as browsers
      from public.client_errors
     where created_at >= p_since
     group by release, path, name
     limit 200
  ) g
$$;

-- ---------------------------------------------------------------------------------------------
-- Pruning (the cron sweep): client errors after 30 days, product events after 13 months.
-- ---------------------------------------------------------------------------------------------

create or replace function public.product_events_retention_days() returns integer
language sql immutable set search_path = '' as $$ select 395 $$;

create or replace function public.prune_ops_data() returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_errors integer;
  v_events integer;
begin
  delete from public.client_errors where created_at < now() - interval '30 days';
  get diagnostics v_errors = row_count;
  delete from public.product_events
   where id in (select id from public.product_events
                 where created_at < now() - make_interval(days => public.product_events_retention_days())
                 limit 5000);
  get diagnostics v_events = row_count;
  return jsonb_build_object('client_errors', v_errors, 'product_events', v_events);
end $$;

-- ---------------------------------------------------------------------------------------------
-- Owner alerts
-- ---------------------------------------------------------------------------------------------

create table public.owner_alert_state (
  kind         text primary key check (kind ~ '^[a-z_]{3,40}$'),
  last_sent_at timestamptz not null,
  sent_count   integer not null default 1
);

-- True for exactly one caller per kind per interval (the mail is sent only after a true).
create or replace function public.claim_owner_alert(p_kind text, p_min_interval_seconds integer) returns boolean
language plpgsql
set search_path = ''
as $$
declare
  v_n integer;
begin
  insert into public.owner_alert_state (kind, last_sent_at) values (p_kind, now())
  on conflict (kind) do update set last_sent_at = now(), sent_count = public.owner_alert_state.sent_count + 1
   where public.owner_alert_state.last_sent_at <= now() - make_interval(secs => greatest(p_min_interval_seconds, 60));
  get diagnostics v_n = row_count;
  return v_n > 0;
end $$;

-- What the 5-minute alert check looks at. Admin accounts' renders count here (a broken worker is broken for all).
create or replace function public.ops_alert_signals() returns jsonb
language sql stable
set search_path = ''
as $$
  select jsonb_build_object(
    'worker_misconfigured', (select count(*) from public.render_jobs
                              where error_code = 'WORKER_MISCONFIGURED' and finished_at > now() - interval '1 hour'),
    'recent', (select jsonb_build_object('finished', count(*), 'failed', count(*) filter (where status = 'failed'))
                 from (select status from public.render_jobs
                        where status in ('succeeded', 'failed') and finished_at is not null
                        order by finished_at desc limit 20) r),
    'webhook_errors', (select count(*) from public.billing_webhook_errors where received_at > now() - interval '1 hour'),
    'gpu_seconds_today', public.gpu_seconds_today(),
    'daily_gpu_budget_seconds', public.setting_value('daily_gpu_budget_seconds'),
    'active_renders', (select count(*) from public.render_jobs where status in ('queued', 'running')),
    'global_max_active_renders', public.setting_value('global_max_active_renders')
  )
$$;

-- The daily digest: the last p_since..now, admins excluded.
create or replace function public.ops_daily_digest(p_since timestamptz) returns jsonb
language sql stable
set search_path = ''
as $$
  with jobs as (
    select j.* from public.render_jobs j
     where j.created_at >= p_since and not exists (select 1 from public.admins a where a.user_id = j.user_id)
  )
  select jsonb_build_object(
    'since', p_since,
    'until', now(),
    'signups', (select count(*) from public.profiles p
                 where p.created_at >= p_since and not exists (select 1 from public.admins a where a.user_id = p.id)),
    'renders', (select jsonb_build_object(
                  'total', count(*),
                  'succeeded', count(*) filter (where status = 'succeeded'),
                  'failed', count(*) filter (where status = 'failed'),
                  'cancelled', count(*) filter (where status = 'cancelled'),
                  'in_flight', count(*) filter (where status in ('queued', 'running')),
                  'gpu_seconds', round(coalesce(sum(gpu_seconds), 0)::numeric, 1),
                  'cost_usd', round(coalesce(sum(cost_usd_estimate), 0), 2))
                from jobs),
    'failures_by_code', coalesce((select jsonb_object_agg(c.code, c.n) from (
                  select coalesce(error_code, 'UNKNOWN') as code, count(*) as n from jobs
                   where status = 'failed' group by 1 order by 2 desc limit 12) c), '{}'::jsonb),
    'refunds', jsonb_build_object(
                  'render_credits', (select coalesce(sum(amount), 0) from public.credit_ledger
                                      where reason = 'render_refund' and created_at >= p_since),
                  'billing_adjustments', (select count(*) from public.billing_adjustments where created_at >= p_since)),
    'revenue', coalesce((select jsonb_agg(jsonb_build_object('currency', r.currency, 'gross_minor', r.gross, 'transactions', r.n))
                  from (select coalesce(currency_code, '?') as currency, sum(total_minor)::bigint as gross, count(*) as n
                          from public.billing_transactions where created_at >= p_since group by 1) r), '[]'::jsonb),
    'webhook_errors', (select count(*) from public.billing_webhook_errors where received_at >= p_since),
    'client_errors', (select count(*) from public.client_errors where created_at >= p_since),
    'paused', coalesce((select jsonb_agg(key order by key) from public.feature_flags where kind = 'flag' and not enabled), '[]'::jsonb)
  )
$$;

-- ---------------------------------------------------------------------------------------------
-- Growth (/admin -> Growth). p_prices: {"creator": <monthly price, minor units>, "pro": ...} from lib/pricing.ts.
-- ---------------------------------------------------------------------------------------------

create or replace function public.admin_growth(p_prices jsonb, p_funnel_days integer default 30) returns jsonb
language plpgsql stable
set search_path = ''
as $$
declare
  v_week  timestamptz := date_trunc('week', now() at time zone 'utc') at time zone 'utc';
  v_day   timestamptz := date_trunc('day', now() at time zone 'utc') at time zone 'utc';
  v_days  integer := least(greatest(coalesce(p_funnel_days, 30), 1), 365);
  v_since timestamptz;
begin
  v_since := now() - make_interval(days => v_days);
  return (
  with gu as (
    select p.id, p.created_at, p.signup_source as source from public.profiles p
     where not exists (select 1 from public.admins a where a.user_id = p.id)
  ), gj as (
    select j.user_id, j.kind::text as kind, j.status::text as status, j.created_at, j.finished_at,
           j.refunded_credits as refunded, j.gpu_seconds, j.cost_usd_estimate as cost
      from public.render_jobs j
     where not exists (select 1 from public.admins a where a.user_id = j.user_id)
  )
  select jsonb_build_object(
    'generated_at', now(),
    'north_star', jsonb_build_object(
      'label', 'Weekly delivered renders',
      'weeks', (select jsonb_agg(jsonb_build_object(
                   'week', w.wk,
                   'renders', (select count(*) from gj j where j.status = 'succeeded' and j.refunded = 0
                                  and j.finished_at >= w.wk and j.finished_at < w.wk + interval '7 days'),
                   'finals', (select count(*) from gj j where j.status = 'succeeded' and j.refunded = 0 and j.kind = 'final'
                                  and j.finished_at >= w.wk and j.finished_at < w.wk + interval '7 days'),
                   'users', (select count(distinct j.user_id) from gj j where j.status = 'succeeded' and j.refunded = 0
                                  and j.finished_at >= w.wk and j.finished_at < w.wk + interval '7 days'))
                 order by w.wk)
                from (select v_week - make_interval(weeks => g) as wk from generate_series(11, 0, -1) g) w)),
    'signups', jsonb_build_object(
      'today', (select count(*) from gu where created_at >= v_day),
      'd7', (select count(*) from gu where created_at >= now() - interval '7 days'),
      'd30', (select count(*) from gu where created_at >= now() - interval '30 days'),
      'by_day', (select jsonb_agg(jsonb_build_object('day', d.day,
                   'n', (select count(*) from gu u where u.created_at >= d.day and u.created_at < d.day + interval '1 day'))
                   order by d.day)
                 from (select v_day - make_interval(days => g) as day from generate_series(29, 0, -1) g) d)),
    -- Signups 7..90 days old with a delivered render (preview or final) within 7 days of signing up.
    'activation', (select jsonb_build_object('cohort', count(*),
                     'activated', count(*) filter (where exists (select 1 from gj j where j.user_id = u.id
                                     and j.status = 'succeeded' and j.finished_at < u.created_at + interval '7 days')),
                     'rate', case when count(*) = 0 then null else round((count(*) filter (where exists (
                                     select 1 from gj j where j.user_id = u.id and j.status = 'succeeded'
                                        and j.finished_at < u.created_at + interval '7 days')))::numeric / count(*), 4) end)
                   from gu u
                   where u.created_at < now() - interval '7 days' and u.created_at >= now() - interval '90 days'),
    -- Signups in the last 90 days: median time from signup to the first delivered render.
    'time_to_first_render', (select jsonb_build_object('users', count(*),
                     'median_seconds', round((percentile_cont(0.5) within group (order by extract(epoch from f.first - u.created_at)))::numeric, 0))
                   from gu u
                   join (select user_id, min(finished_at) as first from gj where status = 'succeeded' group by user_id) f
                     on f.user_id = u.id
                   where u.created_at >= now() - interval '90 days'),
    -- Signups 30..180 days old that paid within 30 days.
    'conversion', (select jsonb_build_object('cohort', count(*),
                     'paid', count(*) filter (where exists (select 1 from public.billing_transactions t where t.user_id = u.id
                                     and t.total_minor > 0 and t.created_at < u.created_at + interval '30 days')),
                     'rate', case when count(*) = 0 then null else round((count(*) filter (where exists (
                                     select 1 from public.billing_transactions t where t.user_id = u.id and t.total_minor > 0
                                        and t.created_at < u.created_at + interval '30 days')))::numeric / count(*), 4) end,
                     'paying_now', (select count(distinct s.user_id) from public.billing_subscriptions s
                                     where s.status in ('active', 'past_due') and s.paid_through is not null
                                       and (s.revoked_through is null or s.revoked_through <= now())))
                   from gu u
                   where u.created_at < now() - interval '30 days' and u.created_at >= now() - interval '180 days'),
    -- Live paid subscriptions that will renew, at the list price.
    'mrr', (select jsonb_build_object('currency', 'USD',
               'minor', coalesce(sum(coalesce((p_prices ->> s.plan::text)::bigint, 0)), 0),
               'subscriptions', count(*),
               'by_plan', coalesce((select jsonb_object_agg(x.plan, x.n) from (
                            select s2.plan::text as plan, count(*) as n from public.billing_subscriptions s2
                             where s2.status in ('active', 'past_due') and s2.paid_through is not null
                               and (s2.revoked_through is null or s2.revoked_through <= now())
                               and coalesce(s2.scheduled_change ->> 'action', '') <> 'cancel'
                             group by 1) x), '{}'::jsonb))
             from public.billing_subscriptions s
             where s.status in ('active', 'past_due') and s.paid_through is not null
               and (s.revoked_through is null or s.revoked_through <= now())
               and coalesce(s.scheduled_change ->> 'action', '') <> 'cancel'),
    'render_success', (select jsonb_build_object(
                     'finished', count(*),
                     'succeeded', count(*) filter (where status = 'succeeded'),
                     'rate', case when count(*) = 0 then null
                                  else round((count(*) filter (where status = 'succeeded'))::numeric / count(*), 4) end)
                   from gj where status in ('succeeded', 'failed') and finished_at >= now() - interval '7 days'),
    'cost', (select jsonb_build_object(
               'renders', count(*),
               'priced', count(cost),
               'avg_usd', round(avg(cost), 4),
               'total_usd', round(coalesce(sum(cost), 0), 2),
               'avg_gpu_seconds', round(avg(gpu_seconds)::numeric, 1))
             from gj where status = 'succeeded' and finished_at >= now() - interval '30 days'),
    -- Any product event on day 1, during days 7-13, during days 30-59 after signup (signups of the last 180 days old
    -- enough to have had the chance).
    'retention', jsonb_build_object(
      'd1', (select jsonb_build_object('cohort', count(*), 'retained', count(*) filter (where exists (
                select 1 from public.product_events e where e.user_id = u.id
                   and e.created_at >= u.created_at + interval '1 day' and e.created_at < u.created_at + interval '2 days')))
             from gu u where u.created_at < now() - interval '2 days' and u.created_at >= now() - interval '180 days'),
      'd7', (select jsonb_build_object('cohort', count(*), 'retained', count(*) filter (where exists (
                select 1 from public.product_events e where e.user_id = u.id
                   and e.created_at >= u.created_at + interval '7 days' and e.created_at < u.created_at + interval '14 days')))
             from gu u where u.created_at < now() - interval '14 days' and u.created_at >= now() - interval '180 days'),
      'd30', (select jsonb_build_object('cohort', count(*), 'retained', count(*) filter (where exists (
                select 1 from public.product_events e where e.user_id = u.id
                   and e.created_at >= u.created_at + interval '30 days' and e.created_at < u.created_at + interval '60 days')))
             from gu u where u.created_at < now() - interval '60 days' and u.created_at >= now() - interval '180 days')),
    'sources', coalesce((select jsonb_agg(jsonb_build_object('source', s.source, 'signups', s.signups, 'paid', s.paid)
                                          order by s.signups desc)
               from (select coalesce(nullif(u.source ->> 'source', ''),
                                     case when u.source ->> 'ref' like 'share\_%' then 'share'
                                          when u.source ? 'ref' then 'ref:' || (u.source ->> 'ref') end,
                                     nullif(u.source ->> 'referrer', ''), 'direct') as source,
                            count(*) as signups,
                            count(*) filter (where exists (select 1 from public.billing_transactions t
                                                            where t.user_id = u.id and t.total_minor > 0)) as paid
                       from gu u where u.created_at >= now() - interval '90 days'
                      group by 1 order by 2 desc limit 10) s), '[]'::jsonb),
    'funnel', jsonb_build_object('days', v_days, 'steps', jsonb_build_array(
      jsonb_build_object('event', 'landing_view', 'count', (select count(distinct session_id) from public.product_events
                            where event = 'landing_view' and created_at >= v_since)),
      jsonb_build_object('event', 'signup_start', 'count', (select count(distinct coalesce(user_id::text, session_id)) from public.product_events
                            where event = 'signup_start' and created_at >= v_since)),
      jsonb_build_object('event', 'signup_complete', 'count', (select count(distinct e.user_id) from public.product_events e
                            where e.event = 'signup_complete' and e.created_at >= v_since
                              and not exists (select 1 from public.admins a where a.user_id = e.user_id))),
      jsonb_build_object('event', 'upload_ready', 'count', (select count(distinct e.user_id) from public.product_events e
                            where e.event = 'upload_ready' and e.created_at >= v_since
                              and not exists (select 1 from public.admins a where a.user_id = e.user_id))),
      jsonb_build_object('event', 'render_requested', 'count', (select count(distinct e.user_id) from public.product_events e
                            where e.event = 'render_requested' and e.created_at >= v_since
                              and not exists (select 1 from public.admins a where a.user_id = e.user_id))),
      jsonb_build_object('event', 'render_succeeded', 'count', (select count(distinct e.user_id) from public.product_events e
                            where e.event = 'render_succeeded' and e.created_at >= v_since
                              and not exists (select 1 from public.admins a where a.user_id = e.user_id))),
      jsonb_build_object('event', 'checkout_complete', 'count', (select count(distinct e.user_id) from public.product_events e
                            where e.event = 'checkout_complete' and e.created_at >= v_since
                              and not exists (select 1 from public.admins a where a.user_id = e.user_id))))),
    -- Weekly signup cohorts (last 8 weeks) x weeks since signup: users with any product event that week.
    'cohorts', (select jsonb_agg(jsonb_build_object('week', c.wk, 'size', c.size, 'active', c.active) order by c.wk)
                from (select w.wk,
                             (select count(*) from gu u where u.created_at >= w.wk and u.created_at < w.wk + interval '7 days') as size,
                             (select jsonb_agg((select count(distinct e.user_id) from public.product_events e
                                                  join gu u on u.id = e.user_id
                                                 where u.created_at >= w.wk and u.created_at < w.wk + interval '7 days'
                                                   and e.created_at >= w.wk + make_interval(weeks => n)
                                                   and e.created_at < w.wk + make_interval(weeks => n + 1)) order by n)
                                from generate_series(0, ((extract(epoch from v_week - w.wk) / 604800)::integer)) n) as active
                        from (select v_week - make_interval(weeks => g) as wk from generate_series(7, 0, -1) g) w) c)
  ));
end $$;

-- ---------------------------------------------------------------------------------------------
-- Privileges + RLS
-- ---------------------------------------------------------------------------------------------

alter table public.product_events    enable row level security;
alter table public.feature_flags     enable row level security;
alter table public.client_errors     enable row level security;
alter table public.owner_alert_state enable row level security;

revoke all on public.product_events, public.feature_flags, public.client_errors, public.owner_alert_state
  from anon, authenticated;
revoke all on sequence public.product_events_id_seq, public.client_errors_id_seq from anon, authenticated;
-- product_events: insert, read and prune only (no UPDATE, not even the service role: append-only).
grant select, insert, delete on public.product_events to service_role;
grant select, insert, update, delete on public.feature_flags, public.client_errors, public.owner_alert_state to service_role;
grant usage, select on sequence public.product_events_id_seq, public.client_errors_id_seq to service_role;

-- The two trigger paths that do not run as the service role get exactly their one event:
--   * projects are inserted by the user (RLS): first_project for themselves, once (unique index).
--   * auth.users triggers run as supabase_auth_admin: signup_complete, and reading the signups kill switch.
grant insert on public.product_events to authenticated, supabase_auth_admin;
create policy product_events_first_project on public.product_events
  for insert to authenticated
  with check (event = 'first_project' and user_id = (select auth.uid()) and source = 'server'
              and session_id is null and path is null and props = '{}'::jsonb);
create policy product_events_signup_complete on public.product_events
  for insert to supabase_auth_admin
  with check (event = 'signup_complete' and source = 'server' and session_id is null and path is null and props = '{}'::jsonb);
grant select (key, enabled) on public.feature_flags to supabase_auth_admin;
create policy feature_flags_auth_admin_select on public.feature_flags
  for select to supabase_auth_admin using (key = 'signups_enabled');
grant execute on function public.flag_enabled(text) to supabase_auth_admin;
grant execute on function public.product_event_names() to authenticated, supabase_auth_admin;
-- Check constraints run as the writing role: profiles are written by users (name) and the auth triggers.
grant execute on function public.attribution_ok(jsonb) to authenticated, supabase_auth_admin;
-- No other policies: product_events, client_errors, owner_alert_state and feature_flags are service role only.

revoke all on function public.product_event_names() from public, anon;
revoke all on function public.client_event_names() from public, anon, authenticated;
revoke all on function public.product_events_block_update() from public, anon, authenticated;
revoke all on function public.emit_product_event(text, uuid, jsonb) from public, anon, authenticated;
revoke all on function public.record_product_event(text, uuid, jsonb, text) from public, anon, authenticated;
revoke all on function public.client_events_hourly_cap() from public, anon, authenticated;
revoke all on function public.record_client_events(text, uuid, jsonb) from public, anon, authenticated;
revoke all on function public.attribution_ok(jsonb) from public, anon;
revoke all on function public.record_signup_source(uuid, jsonb) from public, anon, authenticated;
revoke all on function public.billing_transactions_fill_source() from public, anon, authenticated;
revoke all on function public.billing_set_transaction_source(text, jsonb) from public, anon, authenticated;
revoke all on function public.product_event_signup_confirmed() from public, anon, authenticated;
revoke all on function public.product_event_first_project() from public, anon;
revoke all on function public.upload_reject_code(text) from public, anon, authenticated;
revoke all on function public.product_event_upload() from public, anon, authenticated;
revoke all on function public.product_event_scene_version() from public, anon, authenticated;
revoke all on function public.product_event_render() from public, anon, authenticated;
revoke all on function public.product_event_share() from public, anon, authenticated;
revoke all on function public.product_event_transaction() from public, anon, authenticated;
revoke all on function public.product_event_subscription() from public, anon, authenticated;
revoke all on function public.set_render_job_cost(uuid, numeric, integer, integer) from public, anon, authenticated;
revoke all on function public.flag_enabled(text) from public, anon, authenticated;
revoke all on function public.setting_value(text) from public, anon, authenticated;
revoke all on function public.gpu_seconds_today() from public, anon, authenticated;
revoke all on function public.render_jobs_capacity_guard() from public, anon, authenticated;
revoke all on function public.signups_guard() from public, anon, authenticated;
revoke all on function public.admin_set_flag(uuid, text, boolean, integer, uuid[], numeric, text, text) from public, anon, authenticated;
revoke all on function public.client_errors_hourly_cap() from public, anon, authenticated;
revoke all on function public.record_client_error(text, text, text, text, text, text) from public, anon, authenticated;
revoke all on function public.admin_client_errors(timestamptz) from public, anon, authenticated;
revoke all on function public.product_events_retention_days() from public, anon, authenticated;
revoke all on function public.prune_ops_data() from public, anon, authenticated;
revoke all on function public.claim_owner_alert(text, integer) from public, anon, authenticated;
revoke all on function public.ops_alert_signals() from public, anon, authenticated;
revoke all on function public.ops_daily_digest(timestamptz) from public, anon, authenticated;
revoke all on function public.admin_growth(jsonb, integer) from public, anon, authenticated;

grant execute on function public.product_event_names() to service_role;
grant execute on function public.client_event_names() to service_role;
grant execute on function public.emit_product_event(text, uuid, jsonb) to service_role;
grant execute on function public.record_product_event(text, uuid, jsonb, text) to service_role;
grant execute on function public.client_events_hourly_cap() to service_role;
grant execute on function public.record_client_events(text, uuid, jsonb) to service_role;
grant execute on function public.attribution_ok(jsonb) to service_role;
grant execute on function public.record_signup_source(uuid, jsonb) to service_role;
grant execute on function public.billing_set_transaction_source(text, jsonb) to service_role;
grant execute on function public.upload_reject_code(text) to service_role;
grant execute on function public.set_render_job_cost(uuid, numeric, integer, integer) to service_role;
grant execute on function public.flag_enabled(text) to service_role;
grant execute on function public.setting_value(text) to service_role;
grant execute on function public.gpu_seconds_today() to service_role;
grant execute on function public.admin_set_flag(uuid, text, boolean, integer, uuid[], numeric, text, text) to service_role;
grant execute on function public.client_errors_hourly_cap() to service_role;
grant execute on function public.record_client_error(text, text, text, text, text, text) to service_role;
grant execute on function public.admin_client_errors(timestamptz) to service_role;
grant execute on function public.product_events_retention_days() to service_role;
grant execute on function public.prune_ops_data() to service_role;
grant execute on function public.claim_owner_alert(text, integer) to service_role;
grant execute on function public.ops_alert_signals() to service_role;
grant execute on function public.ops_daily_digest(timestamptz) to service_role;
grant execute on function public.admin_growth(jsonb, integer) to service_role;
