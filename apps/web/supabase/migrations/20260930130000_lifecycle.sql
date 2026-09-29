-- Valora3D lifecycle lane (2026-09-30): lifecycle email, bounces/complaints, churn, feedback, data export.
--
--   * profiles.email_product_tips   the "Product tips" toggle (Settings -> Notifications). Render notifications keep
--                                   using profiles.email_render_ready; account and billing mail is transactional.
--   * email_log                     one row per lifecycle mail ever sent (user, kind, ref; unique), claimed BEFORE the
--                                   send, released if the send fails. claim_email() also applies the preferences,
--                                   the suppression list and a per-user daily cap, in one place.
--   * email_suppressions            addresses that hard-bounced or complained (Resend webhook). They get no
--                                   non-transactional mail.
--   * render_jobs.expiry_warned_at  a finished render whose "expires soon" mail went out (or was skipped).
--   * cancellation_feedback         the one-question reason from the in-app cancel flow, and what the user chose.
--   * feedback                      in-app bug / idea / question reports. RLS: a user inserts their own rows and can
--                                   read back only (user_id, created_at) of their own rows (the hourly cap needs it);
--                                   never a message, never someone else's.
--   * data_exports                  "Download my data" requests, one per user per 24 hours.
-- Rules from the init migration hold: RLS on every table, no SECURITY DEFINER, search_path '', service role only for
-- functions.

-- ---------------------------------------------------------------------------------------------
-- Preferences
-- ---------------------------------------------------------------------------------------------

alter table public.profiles
  add column email_product_tips boolean not null default true;

grant update (email_product_tips) on public.profiles to authenticated;

-- ---------------------------------------------------------------------------------------------
-- Email log (idempotency + rate limit)
-- ---------------------------------------------------------------------------------------------

-- Mirrors LIFECYCLE_KINDS in lib/email/categories.ts (pinned by a test).
create or replace function public.email_kinds() returns text[]
language sql immutable
set search_path = ''
as $$ select array[
  'welcome', 'activation_nudge', 'tips', 'expiry_warning', 'winback',
  'past_due', 'plan_canceled', 'cancel_scheduled', 'plan_paused'
]::text[] $$;

-- tips: product tips (opt-out); renders: render notifications (opt-out); account: transactional (always sent).
create or replace function public.email_kind_category(p_kind text) returns text
language sql immutable
set search_path = ''
as $$
  select case
    when p_kind in ('welcome', 'activation_nudge', 'tips', 'winback') then 'tips'
    when p_kind = 'expiry_warning' then 'renders'
    else 'account'
  end
$$;

-- Per user per rolling 24 hours: opt-out mail (tips + renders) and transactional mail, counted separately.
create or replace function public.email_daily_cap(p_category text) returns integer
language sql immutable
set search_path = ''
as $$ select case when p_category = 'account' then 6 else 2 end $$;

create table public.email_log (
  id      bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  kind    text not null check (kind = any (public.email_kinds())),
  ref     text not null check (char_length(ref) between 1 and 200),
  sent_at timestamptz not null default now(),
  unique (user_id, kind, ref)
);
create index email_log_user_sent_idx on public.email_log (user_id, sent_at desc);
create index email_log_sent_idx on public.email_log (sent_at desc);

-- ---------------------------------------------------------------------------------------------
-- Suppression list (bounces / complaints)
-- ---------------------------------------------------------------------------------------------

create table public.email_suppressions (
  email      text primary key check (email = lower(email) and char_length(email) between 3 and 254 and position('@' in email) > 1),
  reason     text not null check (reason in ('bounce', 'complaint', 'manual')),
  -- The webhook message id (svix-id) of the event that suppressed it, for tracing.
  event_id   text check (event_id is null or event_id ~ '^[A-Za-z0-9_.:-]{1,100}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.email_suppressed(p_email text) returns boolean
language sql stable
set search_path = ''
as $$ select exists (select 1 from public.email_suppressions where email = lower(btrim(p_email))) $$;

-- Upsert; a complaint outranks a bounce (it is the stronger signal), a manual entry outranks both.
create or replace function public.record_email_suppression(p_email text, p_reason text, p_event_id text)
returns boolean
language plpgsql
set search_path = ''
as $$
declare
  v_email text := lower(btrim(coalesce(p_email, '')));
begin
  if p_reason not in ('bounce', 'complaint', 'manual') or v_email !~ '^[^\s@]+@[^\s@]+$' or char_length(v_email) > 254 then
    raise exception 'invalid suppression' using errcode = '22023';
  end if;
  insert into public.email_suppressions (email, reason, event_id) values (v_email, p_reason, p_event_id)
  on conflict (email) do update
    set reason = case
                   when public.email_suppressions.reason = 'manual' or excluded.reason = 'manual' then 'manual'
                   when public.email_suppressions.reason = 'complaint' or excluded.reason = 'complaint' then 'complaint'
                   else 'bounce' end,
        event_id = excluded.event_id,
        updated_at = now();
  return true;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Claim / release
-- ---------------------------------------------------------------------------------------------

-- Returns 'claimed' (send it now), or why not: 'duplicate' (already sent), 'no_profile', 'suppressed',
-- 'opted_out' (the category is off in Settings) or 'rate_limited' (the daily cap; try again later).
-- Transactional (account) mail ignores preferences and the suppression list, but not the cap.
create or replace function public.claim_email(p_user_id uuid, p_kind text, p_ref text) returns text
language plpgsql
set search_path = ''
as $$
declare
  v_profile public.profiles;
  v_category text := public.email_kind_category(p_kind);
  v_n integer;
begin
  if p_kind is null or not (p_kind = any (public.email_kinds())) then
    raise exception 'unknown email kind' using errcode = '22023';
  end if;
  select * into v_profile from public.profiles where id = p_user_id;
  if not found then return 'no_profile'; end if;
  if exists (select 1 from public.email_log where user_id = p_user_id and kind = p_kind and ref = p_ref) then
    return 'duplicate';
  end if;
  if v_category <> 'account' then
    if public.email_suppressed(v_profile.email) then return 'suppressed'; end if;
    if v_category = 'tips' and not v_profile.email_product_tips then return 'opted_out'; end if;
    if v_category = 'renders' and not v_profile.email_render_ready then return 'opted_out'; end if;
  end if;
  select count(*) into v_n from public.email_log
   where user_id = p_user_id and sent_at > now() - interval '24 hours'
     and (public.email_kind_category(kind) = 'account') = (v_category = 'account');
  if v_n >= public.email_daily_cap(v_category) then return 'rate_limited'; end if;
  insert into public.email_log (user_id, kind, ref) values (p_user_id, p_kind, p_ref)
  on conflict (user_id, kind, ref) do nothing;
  get diagnostics v_n = row_count;
  return case when v_n > 0 then 'claimed' else 'duplicate' end;
end $$;

-- The send failed: forget the claim so the next sweep tries again.
create or replace function public.release_email(p_user_id uuid, p_kind text, p_ref text) returns void
language sql
set search_path = ''
as $$ delete from public.email_log where user_id = p_user_id and kind = p_kind and ref = p_ref $$;

-- ---------------------------------------------------------------------------------------------
-- Who is due which mail (the cron sweep, lib/server/lifecycle.ts)
-- ---------------------------------------------------------------------------------------------

-- When an account became usable: its signup_complete event (email confirmed, or OAuth), else profile creation.
create or replace function public.lifecycle_signups() returns table (user_id uuid, confirmed_at timestamptz)
language sql stable
set search_path = ''
as $$
  select e.user_id, e.created_at from public.product_events e
   where e.event = 'signup_complete' and e.user_id is not null
$$;

-- p_kind: welcome (confirmed in the last 3 days), activation_nudge (confirmed 2-5 days ago, no delivered render yet),
-- tips (confirmed 7-10 days ago, has a delivered render), winback (confirmed, no activity for 30-90 days).
-- Each is sent at most once per account (ref 'once'). Preferences and suppressions are pre-filtered here and applied
-- again by claim_email().
create or replace function public.due_lifecycle_emails(p_kind text, p_limit integer default 50)
returns table (user_id uuid, email text, name text)
language plpgsql stable
set search_path = ''
as $$
#variable_conflict use_column
begin
  if p_kind not in ('welcome', 'activation_nudge', 'tips', 'winback') then
    raise exception 'unknown lifecycle kind' using errcode = '22023';
  end if;
  return query
  with s as (select * from public.lifecycle_signups()),
  base as (
    select p.id, p.email, p.name, s.confirmed_at,
           exists (select 1 from public.render_jobs j where j.user_id = p.id and j.status = 'succeeded') as activated
      from public.profiles p
      join s on s.user_id = p.id
     where p.email_product_tips
       and not public.email_suppressed(p.email)
       and not exists (select 1 from public.email_log l where l.user_id = p.id and l.kind = p_kind and l.ref = 'once')
  ),
  active as (
    select b.*, greatest(
             b.confirmed_at,
             (select max(e.created_at) from public.product_events e where e.user_id = b.id),
             (select max(pr.updated_at) from public.projects pr where pr.user_id = b.id),
             (select max(j.created_at) from public.render_jobs j where j.user_id = b.id)
           ) as last_active
      from base b
     where p_kind = 'winback'
  )
  select b.id, b.email, b.name from base b
   where (p_kind = 'welcome' and b.confirmed_at > now() - interval '3 days')
      or (p_kind = 'activation_nudge' and b.confirmed_at <= now() - interval '2 days'
          and b.confirmed_at > now() - interval '5 days' and not b.activated)
      or (p_kind = 'tips' and b.confirmed_at <= now() - interval '7 days'
          and b.confirmed_at > now() - interval '10 days' and b.activated)
  union all
  select a.id, a.email, a.name from active a
   where a.last_active <= now() - interval '30 days' and a.last_active > now() - interval '90 days'
  limit greatest(1, least(coalesce(p_limit, 50), 200));
end $$;

-- Days before a render's outputs are deleted that its owner is warned: 3 on Free (7-day retention), 7 on paid plans.
create or replace function public.expiry_warning_lead_days(p_retention_days integer) returns integer
language sql immutable
set search_path = ''
as $$ select case when coalesce(p_retention_days, 7) <= 7 then 3 else 7 end $$;

alter table public.render_jobs add column expiry_warned_at timestamptz;

-- One row per user: their delivered renders entering the warning window that have not been warned about yet.
create or replace function public.due_expiry_warnings(p_limit integer default 50)
returns table (user_id uuid, email text, name text, plan text, job_ids uuid[], first_expiry timestamptz, render_count integer,
               retention_days integer)
language sql stable
set search_path = ''
as $$
  with due as (
    select j.id, j.user_id, coalesce(j.finished_at, j.updated_at) + make_interval(days => j.retention_days) as expires_at
      from public.render_jobs j
     where j.status = 'succeeded' and j.expired_at is null and j.expiry_warned_at is null
  )
  select d.user_id, p.email, p.name, p.plan::text, array_agg(d.id order by d.expires_at), min(d.expires_at), count(*)::integer,
         min(j.retention_days)::integer
    from due d
    join public.render_jobs j on j.id = d.id
    join public.profiles p on p.id = d.user_id
   where d.expires_at > now()
     and d.expires_at <= now() + make_interval(days => public.expiry_warning_lead_days(j.retention_days))
   group by d.user_id, p.email, p.name, p.plan
   order by min(d.expires_at)
   limit greatest(1, least(coalesce(p_limit, 50), 200))
$$;

create or replace function public.mark_expiry_warned(p_job_ids uuid[]) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_n integer;
begin
  update public.render_jobs set expiry_warned_at = now()
   where id = any (p_job_ids) and expiry_warned_at is null;
  get diagnostics v_n = row_count;
  return v_n;
end $$;

-- Billing notices from the subscription state the Paddle webhook keeps: past_due (once per billing period) and the
-- final cancellation (once per subscription). Only recent changes, so old history never mails anyone. p_user_id
-- narrows it to one account (the webhook's immediate send); null = everyone (the sweep's backstop).
create or replace function public.due_billing_emails(p_user_id uuid default null, p_limit integer default 50)
returns table (user_id uuid, email text, name text, kind text, ref text, plan text, at timestamptz)
language sql stable
set search_path = ''
as $$
  select * from (
    select s.user_id, p.email, p.name, 'past_due'::text as kind,
           s.id || ':' || coalesce(to_char(s.current_period_end at time zone 'UTC', 'YYYYMMDD'), 'none') as ref,
           s.plan::text, s.current_period_end as at
      from public.billing_subscriptions s
      join public.profiles p on p.id = s.user_id
     where s.status = 'past_due' and s.updated_at > now() - interval '7 days'
       and (p_user_id is null or s.user_id = p_user_id)
    union all
    select s.user_id, p.email, p.name, 'plan_canceled'::text, s.id, s.plan::text, coalesce(s.canceled_at, s.updated_at)
      from public.billing_subscriptions s
      join public.profiles p on p.id = s.user_id
     where s.status = 'canceled' and coalesce(s.canceled_at, s.updated_at) > now() - interval '7 days'
       and (p_user_id is null or s.user_id = p_user_id)
  ) d
  where not exists (select 1 from public.email_log l where l.user_id = d.user_id and l.kind = d.kind and l.ref = d.ref)
  limit greatest(1, least(coalesce(p_limit, 50), 200))
$$;

-- ---------------------------------------------------------------------------------------------
-- Cancellation feedback
-- ---------------------------------------------------------------------------------------------

-- Mirrors CANCEL_REASONS in lib/billing/cancel.ts (pinned by a test).
create table public.cancellation_feedback (
  id              uuid primary key default gen_random_uuid(),
  -- Kept (as null) when the account is deleted: the reason stays, the person is gone.
  user_id         uuid references auth.users (id) on delete set null,
  subscription_id text check (subscription_id is null or subscription_id ~ '^sub_[a-z0-9]+$'),
  plan            public.plan_tier,
  reason          text not null check (reason in
                    ('too_expensive', 'not_using', 'missing_feature', 'quality', 'technical', 'switching', 'temporary', 'other')),
  detail          text check (detail is null or char_length(detail) <= 1000),
  outcome         text not null check (outcome in ('canceled', 'paused', 'downgraded')),
  created_at      timestamptz not null default now()
);
create index cancellation_feedback_created_idx on public.cancellation_feedback (created_at desc);

-- ---------------------------------------------------------------------------------------------
-- In-app feedback
-- ---------------------------------------------------------------------------------------------

create table public.feedback (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid default auth.uid() references auth.users (id) on delete set null,
  kind       text not null check (kind in ('bug', 'idea', 'question')),
  message    text not null check (char_length(btrim(message)) between 3 and 4000),
  -- Route template (/projects/[id]), never a URL with ids or a query.
  page       text check (page is null or (char_length(page) <= 120 and page ~ '^/[A-Za-z0-9/_.\[\]-]*$')),
  release    text check (release is null or release ~ '^[A-Za-z0-9._-]{1,40}$'),
  ua_family  text check (ua_family is null or ua_family ~ '^[a-z_]{1,24}$'),
  status     text not null default 'new' check (status in ('new', 'triaged', 'done')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index feedback_created_idx on public.feedback (created_at desc);
create index feedback_user_idx on public.feedback (user_id, created_at desc);

create trigger feedback_touch before update on public.feedback
  for each row execute function public.touch_updated_at();

-- 5 an hour and 20 a day per account. Runs as the inserting user, who can read (user_id, created_at) of their own rows.
create or replace function public.feedback_rate_limit() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.user_id is not null and (
       (select count(*) from public.feedback f where f.user_id = new.user_id and f.created_at > now() - interval '1 hour') >= 5
    or (select count(*) from public.feedback f where f.user_id = new.user_id and f.created_at > now() - interval '24 hours') >= 20
  ) then
    raise exception 'rate_limited' using errcode = 'P0001';
  end if;
  return new;
end $$;

create trigger feedback_rate_limit before insert on public.feedback
  for each row execute function public.feedback_rate_limit();

-- ---------------------------------------------------------------------------------------------
-- Data export rate limit
-- ---------------------------------------------------------------------------------------------

create table public.data_exports (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);
create index data_exports_user_idx on public.data_exports (user_id, created_at desc);

-- True for at most one export per user per 24 hours.
create or replace function public.claim_data_export(p_user_id uuid) returns boolean
language plpgsql
set search_path = ''
as $$
begin
  perform pg_advisory_xact_lock(hashtext('data_export:' || p_user_id::text));
  if exists (select 1 from public.data_exports where user_id = p_user_id and created_at > now() - interval '24 hours') then
    return false;
  end if;
  insert into public.data_exports (user_id) values (p_user_id);
  return true;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Pruning: email_log keeps the 'once' markers forever (they are what makes a welcome once); the rest 400 days.
-- ---------------------------------------------------------------------------------------------

create or replace function public.prune_lifecycle_data() returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_log integer;
  v_exports integer;
begin
  delete from public.email_log where ref <> 'once' and sent_at < now() - interval '400 days';
  get diagnostics v_log = row_count;
  delete from public.data_exports where created_at < now() - interval '30 days';
  get diagnostics v_exports = row_count;
  return jsonb_build_object('email_log', v_log, 'data_exports', v_exports);
end $$;

-- ---------------------------------------------------------------------------------------------
-- Privileges + RLS
-- ---------------------------------------------------------------------------------------------

alter table public.email_log enable row level security;
alter table public.email_suppressions enable row level security;
alter table public.cancellation_feedback enable row level security;
alter table public.feedback enable row level security;
alter table public.data_exports enable row level security;

revoke all on public.email_log, public.email_suppressions, public.cancellation_feedback, public.feedback,
  public.data_exports from anon, authenticated;
revoke all on sequence public.email_log_id_seq, public.data_exports_id_seq from anon, authenticated;
grant select, insert, update, delete on public.email_log, public.email_suppressions, public.cancellation_feedback,
  public.feedback, public.data_exports to service_role;
grant usage, select on sequence public.email_log_id_seq, public.data_exports_id_seq to service_role;

-- feedback: a signed-in user inserts their own rows (status and timestamps take their defaults), and reads back only
-- (user_id, created_at) of their own rows, which the rate-limit trigger counts. Never a message.
grant insert (kind, message, page, release, ua_family) on public.feedback to authenticated;
grant select (user_id, created_at) on public.feedback to authenticated;
create policy feedback_insert_own on public.feedback
  for insert to authenticated
  with check (user_id = (select auth.uid()) and status = 'new');
create policy feedback_select_own_times on public.feedback
  for select to authenticated
  using (user_id = (select auth.uid()));
-- No other policies: email_log, email_suppressions, cancellation_feedback and data_exports are service role only.

revoke all on function public.email_kinds() from public, anon, authenticated;
revoke all on function public.email_kind_category(text) from public, anon, authenticated;
revoke all on function public.email_daily_cap(text) from public, anon, authenticated;
revoke all on function public.email_suppressed(text) from public, anon, authenticated;
revoke all on function public.record_email_suppression(text, text, text) from public, anon, authenticated;
revoke all on function public.claim_email(uuid, text, text) from public, anon, authenticated;
revoke all on function public.release_email(uuid, text, text) from public, anon, authenticated;
revoke all on function public.lifecycle_signups() from public, anon, authenticated;
revoke all on function public.due_lifecycle_emails(text, integer) from public, anon, authenticated;
revoke all on function public.expiry_warning_lead_days(integer) from public, anon, authenticated;
revoke all on function public.due_expiry_warnings(integer) from public, anon, authenticated;
revoke all on function public.mark_expiry_warned(uuid[]) from public, anon, authenticated;
revoke all on function public.due_billing_emails(uuid, integer) from public, anon, authenticated;
revoke all on function public.feedback_rate_limit() from public, anon;
revoke all on function public.claim_data_export(uuid) from public, anon, authenticated;
revoke all on function public.prune_lifecycle_data() from public, anon, authenticated;

-- The email_log check constraint runs as the writing role (service role only).
grant execute on function public.email_kinds() to service_role;
grant execute on function public.email_kind_category(text) to service_role;
grant execute on function public.email_daily_cap(text) to service_role;
grant execute on function public.email_suppressed(text) to service_role;
grant execute on function public.record_email_suppression(text, text, text) to service_role;
grant execute on function public.claim_email(uuid, text, text) to service_role;
grant execute on function public.release_email(uuid, text, text) to service_role;
grant execute on function public.lifecycle_signups() to service_role;
grant execute on function public.due_lifecycle_emails(text, integer) to service_role;
grant execute on function public.expiry_warning_lead_days(integer) to service_role;
grant execute on function public.due_expiry_warnings(integer) to service_role;
grant execute on function public.mark_expiry_warned(uuid[]) to service_role;
grant execute on function public.due_billing_emails(uuid, integer) to service_role;
grant execute on function public.feedback_rate_limit() to authenticated, service_role;
grant execute on function public.claim_data_export(uuid) to service_role;
grant execute on function public.prune_lifecycle_data() to service_role;
