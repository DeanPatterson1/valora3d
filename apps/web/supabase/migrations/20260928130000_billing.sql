-- Valora3D billing (Lane C, 2026-09-28): Paddle Billing -> credit ledger + plans.
--
-- Rules (docs/launch-plan.md, "Security rules"):
--   * Credits are granted only by a verified Paddle webhook. The API route verifies the signature,
--     maps the event to one "action" (lib/billing/events.ts) and calls billing_apply_event() once:
--     the event id is recorded and the action applied in the SAME transaction, so a replay is a
--     no-op and a failure leaves nothing behind for Paddle's retry to trip over.
--   * Every ledger row a payment writes has a unique ref:
--       'paddle:txn:<txn_id>'                              credit pack purchase
--       'paddle:sub:<sub_id>:<period_end_epoch>:<plan>'    monthly plan grant (one per billing period;
--                                                          an upgrade mid-period tops up the difference)
--       'paddle:adj:<adj_id>'                              refund / chargeback (negative) or its reversal
--   * Unmatched grants and reversals raise, so the webhook answers 500 and Paddle retries.
--   * A refund or chargeback may take the balance below zero. create_render_job / spend_credits
--     already refuse any new spend while the balance is below the cost, and a negative balance is
--     below every cost (including 0), so renders are blocked until the account is back above zero.
--   * No SECURITY DEFINER. Everything here is service_role only, like the init migration.

-- ---------------------------------------------------------------------------------------------
-- Ledger: one more reason for payment reversals.
-- ---------------------------------------------------------------------------------------------

alter table public.credit_ledger drop constraint credit_ledger_reason_check;
alter table public.credit_ledger add constraint credit_ledger_reason_check check (reason in (
  'signup_grant', 'plan_grant', 'pack_purchase',
  'scene_generation', 'prompt_edit', 'preview_render', 'render_final',
  'render_refund', 'admin_adjustment', 'billing_reversal'));

-- ---------------------------------------------------------------------------------------------
-- Plan limits. Mirrors PLAN_LIMITS in lib/pricing.ts (lib/pricing.test.ts pins both).
-- The render lane calls public.user_plan_limits(user_id) (or plan_limits(plan)) server-side.
-- ---------------------------------------------------------------------------------------------

create or replace function public.plan_limits(p_plan public.plan_tier)
returns table (max_resolution text, watermark boolean, retention_days integer, priority integer)
language sql immutable parallel safe
set search_path = ''
as $$
  select l.max_resolution, l.watermark, l.retention_days, l.priority from (values
    ('free'::public.plan_tier,    '720p',  true,  7,  0),
    ('creator'::public.plan_tier, '1080p', false, 30, 1),
    ('pro'::public.plan_tier,     '4k',    false, 90, 2)
  ) as l(plan, max_resolution, watermark, retention_days, priority)
  where l.plan = p_plan
$$;

-- ---------------------------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------------------------

-- The Paddle customer behind a user (latest one wins). Used for the customer portal.
create table public.billing_customers (
  user_id            uuid primary key references auth.users (id) on delete cascade,
  paddle_customer_id text not null unique check (paddle_customer_id ~ '^ctm_[a-z0-9]+$'),
  updated_at         timestamptz not null default now()
);

create table public.billing_subscriptions (
  id                   text primary key check (id ~ '^sub_[a-z0-9]+$'),
  user_id              uuid not null references auth.users (id) on delete cascade,
  customer_id          text,
  plan                 public.plan_tier not null check (plan <> 'free'),
  price_id             text,
  status               text not null check (status in ('active', 'trialing', 'past_due', 'paused', 'canceled')),
  current_period_start timestamptz,
  current_period_end   timestamptz,
  -- End of the last billing period that was actually paid (from completed transactions). A
  -- canceled / past_due / paused subscription keeps its plan until then, then falls to Free.
  paid_through         timestamptz,
  -- Set when the payment for a period is fully refunded or charged back: no plan until then.
  revoked_through      timestamptz,
  scheduled_change     jsonb,
  canceled_at          timestamptz,
  -- data.updated_at of the last subscription event applied; older events are ignored (Paddle
  -- does not guarantee delivery order).
  source_updated_at    timestamptz,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);
create index billing_subscriptions_user_idx on public.billing_subscriptions (user_id);

-- Every completed Paddle transaction that granted credits, so a refund knows what to take back.
create table public.billing_transactions (
  id               text primary key check (id ~ '^txn_[a-z0-9]+$'),
  user_id          uuid not null references auth.users (id) on delete cascade,
  kind             text not null check (kind in ('pack', 'subscription')),
  subscription_id  text,
  customer_id      text,
  plan             public.plan_tier,
  credits_granted  integer not null check (credits_granted >= 0),
  credits_reversed integer not null default 0 check (credits_reversed between 0 and credits_granted),
  total_minor      bigint not null default 0 check (total_minor >= 0),
  currency_code    text,
  period_start     timestamptz,
  period_end       timestamptz,
  created_at       timestamptz not null default now()
);
create index billing_transactions_user_idx on public.billing_transactions (user_id, created_at desc);
create index billing_transactions_sub_period_idx on public.billing_transactions (subscription_id, period_end);

-- Refunds / chargebacks (and their reversals) that were applied to the ledger.
create table public.billing_adjustments (
  id             text primary key check (id ~ '^adj_[a-z0-9]+$'),
  transaction_id text not null,
  user_id        uuid not null references auth.users (id) on delete cascade,
  action         text not null,
  credits        integer not null,
  created_at     timestamptz not null default now()
);

-- Webhook idempotency + audit: one row per Paddle event id ever processed.
create table public.billing_events (
  event_id    text primary key check (event_id ~ '^evt_[a-z0-9]+$'),
  event_type  text not null,
  occurred_at timestamptz,
  received_at timestamptz not null default now(),
  -- granted | synced | reversed | ignored | stale | unmatched | duplicate_txn
  outcome     text not null default 'pending',
  detail      text
);

create trigger billing_subscriptions_touch before update on public.billing_subscriptions
  for each row execute function public.touch_updated_at();
create trigger billing_customers_touch before update on public.billing_customers
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------------------------
-- Privileges + RLS: users may read their own subscription and transactions; nothing else.
-- ---------------------------------------------------------------------------------------------

alter table public.billing_customers     enable row level security;
alter table public.billing_subscriptions enable row level security;
alter table public.billing_transactions  enable row level security;
alter table public.billing_adjustments   enable row level security;
alter table public.billing_events        enable row level security;

revoke all on public.billing_customers, public.billing_subscriptions, public.billing_transactions,
              public.billing_adjustments, public.billing_events
  from anon, authenticated;
grant select on public.billing_subscriptions, public.billing_transactions to authenticated;
grant all on public.billing_customers, public.billing_subscriptions, public.billing_transactions,
             public.billing_adjustments, public.billing_events
  to service_role;

create policy billing_subscriptions_select_own on public.billing_subscriptions
  for select to authenticated using (user_id = (select auth.uid()));
create policy billing_transactions_select_own on public.billing_transactions
  for select to authenticated using (user_id = (select auth.uid()));

-- ---------------------------------------------------------------------------------------------
-- Effective plan
-- ---------------------------------------------------------------------------------------------

-- The plan a user is entitled to right now: the best subscription that is active/trialing, or
-- that was paid through a date still in the future (a canceled, past_due or paused subscription
-- keeps its plan until the end of the last paid period), unless that period's payment was
-- refunded or charged back. Otherwise Free.
create or replace function public.user_plan(p_user_id uuid) returns public.plan_tier
language sql stable
set search_path = ''
as $$
  select coalesce(
    (select s.plan from public.billing_subscriptions s
      where s.user_id = p_user_id
        and (s.status in ('active', 'trialing') or s.paid_through > now())
        and (s.revoked_through is null or s.revoked_through <= now())
      order by s.plan desc
      limit 1),
    'free'::public.plan_tier)
$$;

-- Limits for a user's effective plan. This is the call the render lane makes.
create or replace function public.user_plan_limits(p_user_id uuid)
returns table (plan public.plan_tier, max_resolution text, watermark boolean, retention_days integer, priority integer)
language sql stable
set search_path = ''
as $$
  select p.plan, l.max_resolution, l.watermark, l.retention_days, l.priority
  from (select public.user_plan(p_user_id) as plan) p
  cross join lateral public.plan_limits(p.plan) l
$$;

-- Writes the effective plan onto the profile (what the UI shows). Called after every billing
-- change; safe to call from a scheduled job to catch periods that ended without an event.
create or replace function public.sync_profile_plan(p_user_id uuid) returns public.plan_tier
language plpgsql
set search_path = ''
as $$
declare
  v_plan public.plan_tier := public.user_plan(p_user_id);
begin
  update public.profiles set plan = v_plan where id = p_user_id and plan is distinct from v_plan;
  return v_plan;
end $$;

-- Catches paid periods that ended with no later event (profiles.plan is a display copy; the
-- render lane should read user_plan() / user_plan_limits(), which are always live). Safe to run
-- on a schedule, e.g. `select cron.schedule('sync-plans', '17 * * * *', 'select public.sync_expired_plans()')`.
create or replace function public.sync_expired_plans() returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  update public.profiles p set plan = public.user_plan(p.id)
   where p.plan <> 'free' and p.plan is distinct from public.user_plan(p.id);
  get diagnostics v_count = row_count;
  return v_count;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Applying one webhook event
-- ---------------------------------------------------------------------------------------------

-- Who an event belongs to: the signed user id from custom_data (verified by the API route), else
-- the owner of the subscription. Never the Paddle customer: Paddle.js runs in the browser, so a
-- buyer can check out under someone else's email (= their Paddle customer) and must not be able
-- to credit, or charge back against, that account.
create or replace function public.billing_resolve_user(p_user_id uuid, p_subscription_id text)
returns uuid
language sql stable
set search_path = ''
as $$
  select coalesce(
    (select p.id from public.profiles p where p.id = p_user_id),
    (select s.user_id from public.billing_subscriptions s where s.id = p_subscription_id))
$$;

-- Called by /api/billing/checkout only, with the customer Paddle holds for the account's own
-- verified email. Webhooks never link customers (see billing_resolve_user).
create or replace function public.billing_link_customer(p_user_id uuid, p_customer_id text) returns void
language plpgsql
set search_path = ''
as $$
begin
  if p_customer_id is null or p_customer_id !~ '^ctm_[a-z0-9]+$' then
    return;
  end if;
  -- One customer id maps to one user: an id already linked elsewhere is left alone.
  if exists (select 1 from public.billing_customers where paddle_customer_id = p_customer_id and user_id <> p_user_id) then
    return;
  end if;
  insert into public.billing_customers (user_id, paddle_customer_id) values (p_user_id, p_customer_id)
  on conflict (user_id) do update set paddle_customer_id = excluded.paddle_customer_id
    where public.billing_customers.paddle_customer_id is distinct from excluded.paddle_customer_id;
end $$;

-- p_action shapes (built by lib/billing/events.ts; every field is validated there and here):
--   {"kind":"grant_pack", "user_id", "customer_id", "transaction_id", "credits", "total_minor", "currency_code"}
--   {"kind":"grant_subscription", "user_id", "customer_id", "transaction_id", "subscription_id", "plan",
--    "credits", "period_start", "period_end", "total_minor", "currency_code"}
--   {"kind":"subscription_state", "user_id", "customer_id", "subscription_id", "plan", "price_id", "status",
--    "period_start", "period_end", "scheduled_change", "canceled_at", "updated_at"}
--   {"kind":"reversal", "adjustment_id", "transaction_id", "action", "full", "amount_minor"}
--   {"kind":"ignore", "reason"}
-- Returns {"outcome": ..., ...}. 'duplicate' means this event id was already processed.
create or replace function public.billing_apply_event(
  p_event_id    text,
  p_event_type  text,
  p_occurred_at timestamptz,
  p_action      jsonb
) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_kind     text := p_action ->> 'kind';
  v_inserted integer;
  v_result   jsonb;
begin
  if p_event_id is null or p_event_id !~ '^evt_[a-z0-9]+$' then
    raise exception 'bad event id' using errcode = '22023';
  end if;

  insert into public.billing_events (event_id, event_type, occurred_at)
  values (p_event_id, p_event_type, p_occurred_at)
  on conflict (event_id) do nothing;
  get diagnostics v_inserted = row_count;
  if v_inserted = 0 then
    return jsonb_build_object('outcome', 'duplicate');
  end if;

  v_result := case v_kind
    when 'grant_pack'         then public.billing_grant_pack(p_action)
    when 'grant_subscription' then public.billing_grant_subscription(p_action)
    when 'subscription_state' then public.billing_sync_subscription(p_action)
    when 'reversal'           then public.billing_reverse(p_action)
    when 'ignore'             then jsonb_build_object('outcome', 'ignored', 'detail', p_action ->> 'reason')
  end;
  if v_result is null then
    raise exception 'unknown billing action %', v_kind using errcode = '22023';
  end if;

  update public.billing_events
     set outcome = v_result ->> 'outcome', detail = left(v_result ->> 'detail', 500)
   where event_id = p_event_id;
  return v_result;
end $$;

create or replace function public.billing_grant_pack(p_action jsonb) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_txn     text := p_action ->> 'transaction_id';
  v_credits integer := (p_action ->> 'credits')::integer;
  v_user    uuid;
  v_new     integer;
begin
  if v_txn is null or v_credits is null or v_credits <= 0 then
    raise exception 'bad pack grant' using errcode = '22023';
  end if;
  v_user := public.billing_resolve_user((p_action ->> 'user_id')::uuid, null);
  if v_user is null then
    -- Roll back (the event id too) so the webhook answers 500 and Paddle retries; the errors alert.
    raise exception 'unmatched: no user for %', v_txn using errcode = 'P0002';
  end if;

  perform public.lock_user_credits(v_user);
  insert into public.billing_transactions (id, user_id, kind, customer_id, credits_granted, total_minor, currency_code)
  values (v_txn, v_user, 'pack', p_action ->> 'customer_id', v_credits,
          coalesce((p_action ->> 'total_minor')::bigint, 0), p_action ->> 'currency_code')
  on conflict (id) do nothing;
  get diagnostics v_new = row_count;
  if v_new = 0 then
    return jsonb_build_object('outcome', 'duplicate_txn', 'detail', v_txn);
  end if;

  insert into public.credit_ledger (user_id, amount, reason, ref)
  values (v_user, v_credits, 'pack_purchase', 'paddle:txn:' || v_txn);
  return jsonb_build_object('outcome', 'granted', 'user_id', v_user, 'credits', v_credits);
end $$;

create or replace function public.billing_grant_subscription(p_action jsonb) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_txn        text := p_action ->> 'transaction_id';
  v_sub        text := p_action ->> 'subscription_id';
  v_plan       public.plan_tier := (p_action ->> 'plan')::public.plan_tier;
  v_credits    integer := (p_action ->> 'credits')::integer;
  v_start      timestamptz := (p_action ->> 'period_start')::timestamptz;
  v_end        timestamptz := (p_action ->> 'period_end')::timestamptz;
  v_user       uuid;
  v_already    integer;
  v_first      timestamptz;
  v_fraction   numeric;
  v_amount     integer;
  v_new        integer;
begin
  if v_txn is null or v_sub is null or v_plan = 'free' or v_credits is null or v_credits <= 0 or v_end is null then
    raise exception 'bad subscription grant' using errcode = '22023';
  end if;
  v_user := public.billing_resolve_user((p_action ->> 'user_id')::uuid, v_sub);
  if v_user is null then
    raise exception 'unmatched: no user for %', v_txn using errcode = 'P0002';
  end if;

  perform public.lock_user_credits(v_user);
  if exists (select 1 from public.billing_transactions where id = v_txn) then
    return jsonb_build_object('outcome', 'duplicate_txn', 'detail', v_txn);
  end if;

  -- One plan grant per billing period. An upgrade inside a period (a prorated transaction that
  -- ends with the same period) tops up the difference scaled by the share of the period left,
  -- the same share Paddle charges for. Downgrades are not billed (paddle-api.ts), so add nothing.
  select coalesce(sum(credits_granted), 0)::integer, min(period_start) into v_already, v_first
    from public.billing_transactions
   where subscription_id = v_sub and period_end = v_end;
  if v_already = 0 then
    v_amount := v_credits;
  else
    v_fraction := case
      when v_first is null or v_end <= v_first then 1
      else greatest(0, least(1, extract(epoch from (v_end - greatest(now(), v_first)))
                                / extract(epoch from (v_end - v_first))))
    end;
    v_amount := greatest(ceil((v_credits - v_already) * v_fraction)::integer, 0);
  end if;

  if v_amount > 0 then
    insert into public.credit_ledger (user_id, amount, reason, ref)
    values (v_user, v_amount, 'plan_grant',
            'paddle:sub:' || v_sub || ':' || extract(epoch from v_end)::bigint::text || ':' || v_plan::text)
    on conflict (ref) do nothing;
    get diagnostics v_new = row_count;
    if v_new = 0 then
      v_amount := 0;
    end if;
  end if;

  -- Recorded with what was actually granted, so a refund takes back no more than that.
  insert into public.billing_transactions
    (id, user_id, kind, subscription_id, customer_id, plan, credits_granted, total_minor, currency_code, period_start, period_end)
  values (v_txn, v_user, 'subscription', v_sub, p_action ->> 'customer_id', v_plan, v_amount,
          coalesce((p_action ->> 'total_minor')::bigint, 0), p_action ->> 'currency_code', v_start, v_end);

  -- The subscription is paid through the end of this period. If the subscription.* event has not
  -- arrived yet, start the row from the transaction; the event fills in the rest.
  insert into public.billing_subscriptions (id, user_id, customer_id, plan, status, current_period_start, current_period_end, paid_through)
  values (v_sub, v_user, p_action ->> 'customer_id', v_plan, 'active', v_start, v_end, v_end)
  on conflict (id) do update
    set paid_through = greatest(coalesce(public.billing_subscriptions.paid_through, excluded.paid_through), excluded.paid_through);

  perform public.sync_profile_plan(v_user);
  return jsonb_build_object('outcome', 'granted', 'user_id', v_user, 'credits', v_amount);
end $$;

create or replace function public.billing_sync_subscription(p_action jsonb) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_sub     text := p_action ->> 'subscription_id';
  v_updated timestamptz := (p_action ->> 'updated_at')::timestamptz;
  v_user    uuid;
  v_prev    timestamptz;
  v_plan    public.plan_tier;
begin
  if v_sub is null or (p_action ->> 'plan') is null or (p_action ->> 'status') is null then
    raise exception 'bad subscription state' using errcode = '22023';
  end if;
  v_user := public.billing_resolve_user((p_action ->> 'user_id')::uuid, v_sub);
  if v_user is null then
    -- The first payment (signed) creates the row; this state event is then superseded anyway.
    return jsonb_build_object('outcome', 'unmatched', 'detail', 'no user for ' || v_sub);
  end if;

  -- Serialise with the grant functions and with concurrent deliveries for this user.
  perform public.lock_user_credits(v_user);

  select source_updated_at into v_prev from public.billing_subscriptions where id = v_sub for update;
  if v_prev is not null and v_updated is not null and v_updated < v_prev then
    return jsonb_build_object('outcome', 'stale', 'detail', v_sub);
  end if;

  insert into public.billing_subscriptions
    (id, user_id, customer_id, plan, price_id, status, current_period_start, current_period_end,
     scheduled_change, canceled_at, source_updated_at)
  values (v_sub, v_user, p_action ->> 'customer_id', (p_action ->> 'plan')::public.plan_tier,
          p_action ->> 'price_id', p_action ->> 'status',
          (p_action ->> 'period_start')::timestamptz, (p_action ->> 'period_end')::timestamptz,
          p_action -> 'scheduled_change', (p_action ->> 'canceled_at')::timestamptz, v_updated)
  on conflict (id) do update set
    customer_id          = coalesce(excluded.customer_id, public.billing_subscriptions.customer_id),
    plan                 = excluded.plan,
    price_id             = excluded.price_id,
    status               = excluded.status,
    current_period_start = coalesce(excluded.current_period_start, public.billing_subscriptions.current_period_start),
    current_period_end   = coalesce(excluded.current_period_end, public.billing_subscriptions.current_period_end),
    scheduled_change     = excluded.scheduled_change,
    canceled_at          = excluded.canceled_at,
    source_updated_at    = excluded.source_updated_at
  where excluded.source_updated_at is null
     or public.billing_subscriptions.source_updated_at is null
     or excluded.source_updated_at >= public.billing_subscriptions.source_updated_at;

  v_plan := public.sync_profile_plan(v_user);
  return jsonb_build_object('outcome', 'synced', 'user_id', v_user, 'plan', v_plan);
end $$;

-- Refund / credit / chargeback: take back the credits that transaction granted, in proportion to the
-- amount adjusted (a full adjustment takes back everything still outstanding). A reversed
-- chargeback gives them back. The balance may go negative.
create or replace function public.billing_reverse(p_action jsonb) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_adj    text := p_action ->> 'adjustment_id';
  v_kind   text := p_action ->> 'action';
  v_full   boolean := coalesce((p_action ->> 'full')::boolean, false);
  v_amount bigint := coalesce((p_action ->> 'amount_minor')::bigint, 0);
  v_txn    public.billing_transactions;
  v_share  integer;
  v_delta  integer;
begin
  if v_adj is null or v_kind is null or v_kind not in ('refund', 'credit', 'chargeback', 'chargeback_reverse') then
    raise exception 'bad reversal' using errcode = '22023';
  end if;
  select * into v_txn from public.billing_transactions where id = p_action ->> 'transaction_id' for update;
  if not found then
    -- The grant may still be waiting for Paddle's retry: fail so this adjustment is retried too.
    raise exception 'unmatched: no granted transaction for %', v_adj using errcode = 'P0002';
  end if;
  if exists (select 1 from public.billing_adjustments where id = v_adj) then
    return jsonb_build_object('outcome', 'duplicate_txn', 'detail', v_adj);
  end if;

  perform public.lock_user_credits(v_txn.user_id);
  v_share := case
    when v_full or v_txn.total_minor <= 0 then v_txn.credits_granted
    else least(v_txn.credits_granted, ceil(v_txn.credits_granted::numeric * v_amount / v_txn.total_minor)::integer)
  end;

  if v_kind = 'chargeback_reverse' then
    v_delta := least(v_share, v_txn.credits_reversed);           -- give back, at most what was taken
  else
    v_delta := -least(v_share, v_txn.credits_granted - v_txn.credits_reversed);
  end if;

  insert into public.billing_adjustments (id, transaction_id, user_id, action, credits)
  values (v_adj, v_txn.id, v_txn.user_id, v_kind, v_delta);
  if v_delta <> 0 then
    insert into public.credit_ledger (user_id, amount, reason, ref)
    values (v_txn.user_id, v_delta, 'billing_reversal', 'paddle:adj:' || v_adj);
    update public.billing_transactions set credits_reversed = credits_reversed - v_delta where id = v_txn.id;
  end if;

  -- A fully refunded / charged-back plan payment also removes the plan for that period; a
  -- reversed chargeback restores it.
  if v_txn.kind = 'subscription' and v_txn.subscription_id is not null then
    if v_kind = 'chargeback_reverse' then
      update public.billing_subscriptions set revoked_through = null
       where id = v_txn.subscription_id and revoked_through is not distinct from v_txn.period_end;
    elsif v_full or (v_txn.total_minor > 0 and v_amount >= v_txn.total_minor) then
      update public.billing_subscriptions
         set revoked_through = greatest(coalesce(revoked_through, v_txn.period_end), v_txn.period_end)
       where id = v_txn.subscription_id;
    end if;
    perform public.sync_profile_plan(v_txn.user_id);
  end if;
  return jsonb_build_object('outcome', 'reversed', 'user_id', v_txn.user_id, 'credits', v_delta);
end $$;

-- ---------------------------------------------------------------------------------------------
-- Grants: service role only (plan_limits is harmless constants, readable by signed-in users too).
-- ---------------------------------------------------------------------------------------------

revoke all on function public.plan_limits(public.plan_tier) from public, anon;
revoke all on function public.user_plan(uuid) from public, anon, authenticated;
revoke all on function public.user_plan_limits(uuid) from public, anon, authenticated;
revoke all on function public.sync_profile_plan(uuid) from public, anon, authenticated;
revoke all on function public.sync_expired_plans() from public, anon, authenticated;
revoke all on function public.billing_resolve_user(uuid, text) from public, anon, authenticated;
revoke all on function public.billing_link_customer(uuid, text) from public, anon, authenticated;
revoke all on function public.billing_apply_event(text, text, timestamptz, jsonb) from public, anon, authenticated;
revoke all on function public.billing_grant_pack(jsonb) from public, anon, authenticated;
revoke all on function public.billing_grant_subscription(jsonb) from public, anon, authenticated;
revoke all on function public.billing_sync_subscription(jsonb) from public, anon, authenticated;
revoke all on function public.billing_reverse(jsonb) from public, anon, authenticated;

grant execute on function public.plan_limits(public.plan_tier) to authenticated, service_role;
grant execute on function public.user_plan(uuid) to service_role;
grant execute on function public.user_plan_limits(uuid) to service_role;
grant execute on function public.sync_profile_plan(uuid) to service_role;
grant execute on function public.sync_expired_plans() to service_role;
grant execute on function public.billing_resolve_user(uuid, text) to service_role;
grant execute on function public.billing_link_customer(uuid, text) to service_role;
grant execute on function public.billing_apply_event(text, text, timestamptz, jsonb) to service_role;
grant execute on function public.billing_grant_pack(jsonb) to service_role;
grant execute on function public.billing_grant_subscription(jsonb) to service_role;
grant execute on function public.billing_sync_subscription(jsonb) to service_role;
grant execute on function public.billing_reverse(jsonb) to service_role;
