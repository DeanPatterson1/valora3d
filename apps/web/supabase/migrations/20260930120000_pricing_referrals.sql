-- Valora3D pricing v2 + referrals + plan-credit rollover (pricing lane, 2026-09-30).
--
-- PLACEHOLDER PRICES (pricing v3, owner-approved direction from a blind buyer-panel review; unit: 100 credits = one
-- 1080p final clip); re-derived from the measured p90 GPU cost per clip before launch (docs/launch-plan.md, "Pricing").
--
-- Every price the database knows is a constant function in THIS file, and each mirrors one constant in
-- lib/pricing.ts (lib/pricing.test.ts pins them to each other):
--   free_plan_credits()        FREE_PLAN_CREDITS                 10 (one scene plan + one preview)
--   render_cost(kind)          CREDIT_COSTS.preview_render/final  5 / 100
--   render_failure_fee()       RENDER_FAILURE_FEE                 = the preview price
--   plan_credit_rollover()     PLAN_CREDIT_ROLLOVER_PERIODS       1 month
--   referral_bonus_credits()   REFERRAL_BONUS_CREDITS             100
--   referral_monthly_cap()     REFERRAL_MONTHLY_CAP               20
--   scene_action_cost(action)  stays in 20260929100000_scene_version_credits.sql (5 / 2 / 0: generate / edit / adjust).
-- The server still passes the render price into create_render_job, but a job can no longer be inserted at any
-- other price (render_jobs_price_guard), and an input-failure fee can no longer exceed render_failure_fee().
--
-- Plan-credit rollover: a monthly plan grant expires when the period AFTER the one it was granted for ends
-- (expires_at on the ledger row, derived from its ref). expire_plan_credits(), run by the cron sweep, replays the
-- user's ledger (spends use the soonest-expiring plan credits first, then everything else) and writes one
-- `credit_expiry` row for what is left of each expired grant. Pack credits, the Free grant, referral bonuses,
-- refunds and admin grants never expire.
--
-- Referrals: referral_codes (one per user, made on first ask), referrals (one per referred user). A signup whose
-- first-touch attribution (profiles.signup_source, lib/analytics/attribution.ts) carries ref = u_<code> joins the
-- code owner's referrals. The referred user's FIRST paid transaction (any billing_transactions row: they exist
-- only for paid transactions, billing_hardening L1) pays REFERRAL_BONUS_CREDITS to both, once per referred user
-- (ledger refs 'referral:<referee>:referee' / ':referrer'), the referrer at most referral_monthly_cap() times per
-- calendar month (UTC). Self-referral is refused: the same account, the same normalised email, or the same Paddle
-- customer. A full refund / chargeback of the qualifying payment takes both bonuses back (referral_reversal).
--
-- Rules from earlier migrations hold: RLS on every table, no SECURITY DEFINER, search_path '', service role only
-- for the money-moving functions.

-- ---------------------------------------------------------------------------------------------
-- Constants
-- ---------------------------------------------------------------------------------------------

create or replace function public.free_plan_credits() returns integer
language sql immutable parallel safe
set search_path = ''
as $$ select 10 $$;

create or replace function public.render_cost(p_kind public.render_job_kind) returns integer
language sql immutable parallel safe
set search_path = ''
as $$ select case p_kind when 'preview' then 5 when 'final' then 100 end $$;

create or replace function public.render_failure_fee() returns integer
language sql immutable parallel safe
set search_path = ''
as $$ select public.render_cost('preview') $$;

create or replace function public.plan_credit_rollover() returns interval
language sql immutable parallel safe
set search_path = ''
as $$ select interval '1 month' * 1 $$;

create or replace function public.referral_bonus_credits() returns integer
language sql immutable parallel safe
set search_path = ''
as $$ select 100 $$;

create or replace function public.referral_monthly_cap() returns integer
language sql immutable parallel safe
set search_path = ''
as $$ select 20 $$;

-- ---------------------------------------------------------------------------------------------
-- Ledger: new reasons, expiry date on plan grants
-- ---------------------------------------------------------------------------------------------

alter table public.credit_ledger drop constraint credit_ledger_reason_check;
alter table public.credit_ledger add constraint credit_ledger_reason_check check (reason in (
  'signup_grant', 'plan_grant', 'pack_purchase',
  'scene_generation', 'prompt_edit', 'preview_render', 'render_preview', 'render_final',
  'render_refund', 'admin_adjustment', 'billing_reversal',
  'referral_bonus', 'referral_reversal', 'credit_expiry'));

-- Set once at insert (credit_ledger_block_update keeps it; only plan grants carry one).
alter table public.credit_ledger add column expires_at timestamptz;

-- A plan grant's ref is 'paddle:sub:<sub_id>:<period_end_epoch>:<plan>' (billing_grant_subscription): it expires
-- plan_credit_rollover() after the end of the period it was granted for (calendar months in UTC).
create or replace function public.credit_ledger_set_expiry() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_epoch text := split_part(new.ref, ':', 4);
begin
  if new.reason = 'plan_grant' then
    new.expires_at := case when v_epoch ~ '^[0-9]{1,12}$'
                           then (pg_catalog.to_timestamp(v_epoch::double precision) at time zone 'UTC' + public.plan_credit_rollover()) at time zone 'UTC'
                      end;
  else
    new.expires_at := null;
  end if;
  return new;
end $$;

create trigger credit_ledger_expiry
  before insert on public.credit_ledger
  for each row execute function public.credit_ledger_set_expiry();

create or replace function public.credit_ledger_block_update() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if (new.user_id is distinct from old.user_id and new.user_id is not null)
     or new.amount is distinct from old.amount
     or new.reason is distinct from old.reason
     or new.ref is distinct from old.ref
     or new.expires_at is distinct from old.expires_at
     or new.created_at is distinct from old.created_at then
    raise exception 'credit_ledger is append-only' using errcode = '42501';
  end if;
  return new;
end $$;

-- Plan grants already swept (so a fully used grant is not replayed every day). Service role only.
create table public.plan_grant_sweeps (
  ledger_id bigint primary key references public.credit_ledger (id) on delete cascade,
  expired   integer not null check (expired >= 0),
  swept_at  timestamptz not null default now()
);
alter table public.plan_grant_sweeps enable row level security;
revoke all on public.plan_grant_sweeps from anon, authenticated;
grant select, insert on public.plan_grant_sweeps to service_role;

-- What is left of each of the user's plan grants, replaying the ledger in order: a debit uses the plan grant
-- that expires soonest first, then the never-expiring pool; a new grant first pays off any debt; an expiry row
-- empties its grant. Pure read.
create or replace function public.plan_credit_lots(p_user_id uuid)
returns table (ledger_id bigint, expires_at timestamptz, remaining integer)
language plpgsql stable
set search_path = ''
as $$
declare
  r       record;
  v_ids   bigint[] := '{}';
  v_exp   timestamptz[] := '{}';
  v_rem   integer[] := '{}';
  v_pool  integer := 0;
  v_need  integer;
  v_take  integer;
  v_i     integer;
  v_best  integer;
  v_pay   integer;
begin
  for r in select l.id, l.amount, l.reason, l.ref, l.expires_at from public.credit_ledger l
            where l.user_id = p_user_id order by l.created_at, l.id loop
    if r.reason = 'plan_grant' and r.amount > 0 and r.expires_at is not null then
      v_pay := least(r.amount, greatest(-v_pool, 0));
      v_pool := v_pool + v_pay;
      v_ids := v_ids || r.id; v_exp := v_exp || r.expires_at; v_rem := v_rem || (r.amount - v_pay);
    elsif r.reason = 'credit_expiry' then
      v_i := array_position(v_ids, nullif(split_part(r.ref, ':', 2), '')::bigint);
      if v_i is not null then
        v_rem[v_i] := 0;
      end if;
    elsif r.amount > 0 then
      v_pool := v_pool + r.amount;
    else
      v_need := -r.amount;
      while v_need > 0 loop
        v_best := null;
        for v_i in 1 .. coalesce(array_length(v_ids, 1), 0) loop
          if v_rem[v_i] > 0 and (v_best is null or v_exp[v_i] < v_exp[v_best]) then
            v_best := v_i;
          end if;
        end loop;
        exit when v_best is null;
        v_take := least(v_need, v_rem[v_best]);
        v_rem[v_best] := v_rem[v_best] - v_take;
        v_need := v_need - v_take;
      end loop;
      v_pool := v_pool - v_need;
    end if;
  end loop;
  for v_i in 1 .. coalesce(array_length(v_ids, 1), 0) loop
    ledger_id := v_ids[v_i]; expires_at := v_exp[v_i]; remaining := v_rem[v_i];
    return next;
  end loop;
end $$;

-- The cron sweep: expire what is left of every plan grant whose rollover window has ended. Idempotent (one
-- 'expire:<ledger id>' row per grant, and each swept grant is recorded). Returns the credits expired.
create or replace function public.expire_plan_credits(p_limit integer default 200) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_user  uuid;
  v_lot   record;
  v_total integer := 0;
begin
  for v_user in
    select distinct l.user_id from public.credit_ledger l
     where l.reason = 'plan_grant' and l.expires_at <= now() and l.user_id is not null
       and not exists (select 1 from public.plan_grant_sweeps s where s.ledger_id = l.id)
     limit greatest(coalesce(p_limit, 200), 1)
  loop
    perform public.lock_user_credits(v_user);
    for v_lot in select * from public.plan_credit_lots(v_user) loop
      continue when v_lot.expires_at > now()
        or exists (select 1 from public.plan_grant_sweeps s where s.ledger_id = v_lot.ledger_id);
      if v_lot.remaining > 0 then
        insert into public.credit_ledger (user_id, amount, reason, ref)
        values (v_user, -v_lot.remaining, 'credit_expiry', 'expire:' || v_lot.ledger_id::text)
        on conflict (ref) do nothing;
        v_total := v_total + v_lot.remaining;
      end if;
      insert into public.plan_grant_sweeps (ledger_id, expired) values (v_lot.ledger_id, greatest(v_lot.remaining, 0))
      on conflict (ledger_id) do nothing;
    end loop;
  end loop;
  return v_total;
end $$;

-- Plan credits that will expire, soonest first (for the account page): only grants with something left.
create or replace function public.user_expiring_credits(p_user_id uuid)
returns table (expires_at timestamptz, credits integer)
language sql stable
set search_path = ''
as $$
  select l.expires_at, sum(l.remaining)::integer
    from public.plan_credit_lots(p_user_id) l
   where l.remaining > 0 and l.expires_at > now()
   group by l.expires_at
   order by l.expires_at
$$;

-- ---------------------------------------------------------------------------------------------
-- Render prices enforced in the database
-- ---------------------------------------------------------------------------------------------

-- A render job is either free (a comp, cost 0) or charged exactly the tier's price; its input-failure fee is
-- never more than render_failure_fee().
create or replace function public.render_jobs_price_guard() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' and new.cost_credits <> 0 and new.cost_credits <> public.render_cost(new.kind) then
    raise exception 'price_mismatch: % costs %', new.kind, public.render_cost(new.kind) using errcode = '22023';
  end if;
  if new.fee_credits > public.render_failure_fee() then
    raise exception 'fee above render_failure_fee()' using errcode = '22023';
  end if;
  return new;
end $$;

create trigger render_jobs_price_guard
  before insert or update of fee_credits on public.render_jobs
  for each row execute function public.render_jobs_price_guard();

-- ---------------------------------------------------------------------------------------------
-- First-clip pack: one per account
-- ---------------------------------------------------------------------------------------------

-- Which catalog pack a pack transaction bought, for the pack that is limited to one per account ('first'); null for
-- every other transaction. The checkout route refuses a second purchase up front (409 first_clip_used); this unique
-- index is the backstop for two checkouts opened before the first payment landed. Users read their own rows (RLS),
-- which is how the pricing page knows to hide the offer.
alter table public.billing_transactions add column pack_id text check (pack_id ~ '^[a-z0-9]{1,16}$');
create unique index billing_transactions_first_clip_once on public.billing_transactions (user_id) where pack_id = 'first';

-- billing_grant_pack (from 20260929210000_billing_hardening.sql) plus pack_id. Someone who somehow paid for a second
-- first clip is never charged without credits: the credits are granted and the row is stored without pack_id, so the
-- unique index does not fire; the outcome detail 'first_clip_repeat' flags it for a refund review.
create or replace function public.billing_grant_pack(p_action jsonb) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_txn     text := p_action ->> 'transaction_id';
  v_credits integer := (p_action ->> 'credits')::integer;
  v_pack    text := nullif(p_action ->> 'pack_id', '');
  v_repeat  boolean := false;
  v_user    uuid;
  v_new     integer;
begin
  if v_txn is null or v_credits is null or v_credits <= 0 then
    raise exception 'bad pack grant' using errcode = '22023';
  end if;
  -- L1: a pack nobody paid for (100% discount) grants nothing unless it is an allowlisted promo.
  if not public.billing_action_paid(p_action) then
    return jsonb_build_object('outcome', 'ignored', 'detail', 'unpaid pack ' || v_txn);
  end if;
  v_user := public.billing_resolve_user((p_action ->> 'user_id')::uuid, null);
  if v_user is null then
    -- Roll back (the event id too) so the webhook answers 500 and Paddle retries; the errors alert.
    raise exception 'unmatched: no user for %', v_txn using errcode = 'P0002';
  end if;

  perform public.lock_user_credits(v_user);
  if v_pack = 'first' then
    v_repeat := exists (select 1 from public.billing_transactions t where t.user_id = v_user and t.pack_id = 'first' and t.id <> v_txn);
    if v_repeat then
      v_pack := null;
    end if;
  end if;
  insert into public.billing_transactions (id, user_id, kind, customer_id, credits_granted, total_minor, currency_code, pack_id)
  values (v_txn, v_user, 'pack', p_action ->> 'customer_id', v_credits,
          coalesce((p_action ->> 'total_minor')::bigint, 0), p_action ->> 'currency_code', v_pack)
  on conflict (id) do nothing;
  get diagnostics v_new = row_count;
  if v_new = 0 then
    return jsonb_build_object('outcome', 'duplicate_txn', 'detail', v_txn);
  end if;

  insert into public.credit_ledger (user_id, amount, reason, ref)
  values (v_user, v_credits, 'pack_purchase', 'paddle:txn:' || v_txn);
  perform public.billing_apply_held_adjustments(v_txn);
  return jsonb_build_object('outcome', 'granted', 'user_id', v_user, 'credits', v_credits)
      || case when v_repeat then jsonb_build_object('detail', 'first_clip_repeat') else '{}'::jsonb end;
end $$;

-- ---------------------------------------------------------------------------------------------
-- Referrals
-- ---------------------------------------------------------------------------------------------

create table public.referral_codes (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  code       text not null unique check (code ~ '^[a-z0-9]{10}$'),
  created_at timestamptz not null default now()
);

create table public.referrals (
  referee_id        uuid primary key references auth.users (id) on delete cascade,
  referrer_id       uuid references auth.users (id) on delete set null,
  -- joined -> qualified (first payment, bonuses paid) -> reversed (that payment fully refunded / charged back);
  -- rejected: a self-referral found at payment time.
  status            text not null default 'joined' check (status in ('joined', 'qualified', 'reversed', 'rejected')),
  joined_at         timestamptz not null default now(),
  qualified_at      timestamptz,
  qualifying_txn    text,
  referrer_rewarded boolean not null default false,
  reversed_at       timestamptz,
  check (referee_id <> referrer_id)
);
create index referrals_referrer_idx on public.referrals (referrer_id, qualified_at);
create index referrals_txn_idx on public.referrals (qualifying_txn) where qualifying_txn is not null;

alter table public.referral_codes enable row level security;
alter table public.referrals enable row level security;
revoke all on public.referral_codes, public.referrals from anon, authenticated;
grant select on public.referral_codes to authenticated;
grant select, insert on public.referral_codes to service_role;
grant select, insert, update on public.referrals to service_role;
create policy referral_codes_select_own on public.referral_codes
  for select to authenticated using (user_id = (select auth.uid()));
-- referrals: no user policy (a row names another person's account); counts come from referral_summary().

-- The user's code, made on first ask. Service role (the profile page's server route).
create or replace function public.referral_code(p_user_id uuid) returns text
language plpgsql
set search_path = ''
as $$
declare
  v_code text;
  v_try  integer := 0;
begin
  select code into v_code from public.referral_codes where user_id = p_user_id;
  if found then
    return v_code;
  end if;
  if not exists (select 1 from public.profiles where id = p_user_id) then
    raise exception 'no such user' using errcode = 'P0002';
  end if;
  loop
    v_try := v_try + 1;
    v_code := substr(replace(gen_random_uuid()::text, '-', ''), 1, 10);
    insert into public.referral_codes (user_id, code) values (p_user_id, v_code)
    on conflict do nothing;
    select code into v_code from public.referral_codes where user_id = p_user_id;
    if found then
      return v_code;
    end if;
    if v_try >= 5 then
      raise exception 'could not allocate a referral code' using errcode = '40001';
    end if;
  end loop;
end $$;

-- The referrer behind an attribution ref ('u_<code>'), or null.
create or replace function public.referral_referrer(p_ref text) returns uuid
language sql stable
set search_path = ''
as $$
  select c.user_id from public.referral_codes c
   where p_ref ~ '^u_[a-z0-9]{10}$' and c.code = substr(p_ref, 3)
$$;

-- True when the two accounts are the same person by account or normalised email.
create or replace function public.referral_same_person(p_referrer uuid, p_referee uuid) returns boolean
language sql stable
set search_path = ''
as $$
  select p_referrer = p_referee or exists (
    select 1 from public.profiles a, public.profiles b
     where a.id = p_referrer and b.id = p_referee
       and public.normalized_email_key(a.email) is not null
       and public.normalized_email_key(a.email) = public.normalized_email_key(b.email))
$$;

-- profiles.signup_source is written once (record_signup_source). A ref of u_<code> joins that code's referrals.
create or replace function public.referral_on_signup_source() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_referrer uuid;
begin
  if old.signup_source is not null or new.signup_source is null then
    return new;
  end if;
  v_referrer := public.referral_referrer(new.signup_source ->> 'ref');
  if v_referrer is null or public.referral_same_person(v_referrer, new.id) then
    return new;
  end if;
  insert into public.referrals (referee_id, referrer_id) values (new.id, v_referrer)
  on conflict (referee_id) do nothing;
  return new;
end $$;

create trigger referral_on_signup_source
  after update of signup_source on public.profiles
  for each row execute function public.referral_on_signup_source();

-- The referee's first paid transaction pays both bonuses (billing_transactions rows exist only for paid
-- transactions). Runs inside billing_apply_event's transaction, as the service role.
create or replace function public.referral_on_first_payment() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_ref      public.referrals;
  v_bonus    integer := public.referral_bonus_credits();
  v_rewarded integer;
  v_pay_referrer boolean := false;
begin
  if new.user_id is null then
    return new;
  end if;
  select * into v_ref from public.referrals where referee_id = new.user_id and status = 'joined' for update;
  if not found then
    return new;
  end if;
  if exists (select 1 from public.billing_transactions t where t.user_id = new.user_id and t.id <> new.id) then
    return new;   -- not the first payment (the referral joined after an earlier one): never qualifies
  end if;

  -- Self-referral: the same person (email re-checked now), or the payment came from the referrer's Paddle customer.
  if v_ref.referrer_id is not null and (
       public.referral_same_person(v_ref.referrer_id, new.user_id)
       or (new.customer_id is not null and (
             exists (select 1 from public.billing_customers c where c.user_id = v_ref.referrer_id and c.paddle_customer_id = new.customer_id)
             or exists (select 1 from public.billing_transactions t where t.user_id = v_ref.referrer_id and t.customer_id = new.customer_id)))) then
    update public.referrals set status = 'rejected', qualified_at = now(), qualifying_txn = new.id
     where referee_id = new.user_id;
    return new;
  end if;

  insert into public.credit_ledger (user_id, amount, reason, ref)
  values (new.user_id, v_bonus, 'referral_bonus', 'referral:' || new.user_id::text || ':referee')
  on conflict (ref) do nothing;

  if v_ref.referrer_id is not null then
    perform public.lock_user_credits(v_ref.referrer_id);
    select count(*) into v_rewarded from public.referrals r
     where r.referrer_id = v_ref.referrer_id and r.referrer_rewarded
       and r.qualified_at >= date_trunc('month', now() at time zone 'UTC') at time zone 'UTC';
    v_pay_referrer := v_rewarded < public.referral_monthly_cap();
    if v_pay_referrer then
      insert into public.credit_ledger (user_id, amount, reason, ref)
      values (v_ref.referrer_id, v_bonus, 'referral_bonus', 'referral:' || new.user_id::text || ':referrer')
      on conflict (ref) do nothing;
    end if;
  end if;

  update public.referrals
     set status = 'qualified', qualified_at = now(), qualifying_txn = new.id, referrer_rewarded = v_pay_referrer
   where referee_id = new.user_id;
  return new;
end $$;

create trigger referral_on_first_payment
  after insert on public.billing_transactions
  for each row execute function public.referral_on_first_payment();

-- A full refund / chargeback of the qualifying payment (credits_reversed reaches credits_granted) takes both
-- bonuses back. A later reversed chargeback does not restore them.
create or replace function public.referral_on_reversal() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_ref   public.referrals;
  v_bonus integer := public.referral_bonus_credits();
begin
  if not (new.credits_granted > 0 and new.credits_reversed >= new.credits_granted
          and old.credits_reversed < old.credits_granted) then
    return new;
  end if;
  select * into v_ref from public.referrals where qualifying_txn = new.id and status = 'qualified' for update;
  if not found then
    return new;
  end if;
  if exists (select 1 from public.profiles where id = v_ref.referee_id) then
    insert into public.credit_ledger (user_id, amount, reason, ref)
    values (v_ref.referee_id, -v_bonus, 'referral_reversal', 'referral-reversal:' || v_ref.referee_id::text || ':referee')
    on conflict (ref) do nothing;
  end if;
  if v_ref.referrer_rewarded and v_ref.referrer_id is not null then
    insert into public.credit_ledger (user_id, amount, reason, ref)
    values (v_ref.referrer_id, -v_bonus, 'referral_reversal', 'referral-reversal:' || v_ref.referee_id::text || ':referrer')
    on conflict (ref) do nothing;
  end if;
  update public.referrals set status = 'reversed', reversed_at = now() where referee_id = v_ref.referee_id;
  return new;
end $$;

create trigger referral_on_reversal
  after update of credits_reversed on public.billing_transactions
  for each row execute function public.referral_on_reversal();

-- What the Invite card shows: the code and counts, never who.
create or replace function public.referral_summary(p_user_id uuid) returns jsonb
language sql stable
set search_path = ''
as $$
  select jsonb_build_object(
    'code', (select code from public.referral_codes where user_id = p_user_id),
    'joined', (select count(*) from public.referrals where referrer_id = p_user_id and status <> 'rejected'),
    'qualified', (select count(*) from public.referrals where referrer_id = p_user_id and status = 'qualified'),
    'rewarded_this_month', (select count(*) from public.referrals
                             where referrer_id = p_user_id and referrer_rewarded and status = 'qualified'
                               and qualified_at >= date_trunc('month', now() at time zone 'UTC') at time zone 'UTC'),
    'credits_earned', (select coalesce(sum(amount), 0) from public.credit_ledger
                        where user_id = p_user_id and reason in ('referral_bonus', 'referral_reversal')
                          and ref like 'referral%:referrer'))
$$;

-- ---------------------------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------------------------

revoke all on function public.render_cost(public.render_job_kind) from public, anon;
revoke all on function public.render_failure_fee() from public, anon;
revoke all on function public.plan_credit_rollover() from public, anon;
revoke all on function public.referral_bonus_credits() from public, anon;
revoke all on function public.referral_monthly_cap() from public, anon;
grant execute on function public.render_cost(public.render_job_kind) to authenticated, service_role;
grant execute on function public.render_failure_fee() to authenticated, service_role;
grant execute on function public.plan_credit_rollover() to authenticated, service_role, supabase_auth_admin;
grant execute on function public.referral_bonus_credits() to authenticated, service_role;
grant execute on function public.referral_monthly_cap() to authenticated, service_role;

-- The signup grant runs as supabase_auth_admin and passes through the expiry trigger.
revoke all on function public.credit_ledger_set_expiry() from public, anon, authenticated;
grant execute on function public.credit_ledger_set_expiry() to supabase_auth_admin, service_role;

revoke all on function public.render_jobs_price_guard() from public, anon, authenticated;
revoke all on function public.plan_credit_lots(uuid) from public, anon, authenticated;
revoke all on function public.expire_plan_credits(integer) from public, anon, authenticated;
revoke all on function public.user_expiring_credits(uuid) from public, anon, authenticated;
revoke all on function public.referral_code(uuid) from public, anon, authenticated;
revoke all on function public.referral_referrer(text) from public, anon, authenticated;
revoke all on function public.referral_same_person(uuid, uuid) from public, anon, authenticated;
revoke all on function public.referral_on_signup_source() from public, anon, authenticated;
revoke all on function public.referral_on_first_payment() from public, anon, authenticated;
revoke all on function public.referral_on_reversal() from public, anon, authenticated;
revoke all on function public.referral_summary(uuid) from public, anon, authenticated;
revoke all on function public.billing_grant_pack(jsonb) from public, anon, authenticated;
grant execute on function public.render_jobs_price_guard() to service_role;
grant execute on function public.plan_credit_lots(uuid) to service_role;
grant execute on function public.expire_plan_credits(integer) to service_role;
grant execute on function public.user_expiring_credits(uuid) to service_role;
grant execute on function public.referral_code(uuid) to service_role;
grant execute on function public.referral_referrer(text) to service_role;
grant execute on function public.referral_same_person(uuid, uuid) to service_role;
grant execute on function public.referral_on_signup_source() to service_role;
grant execute on function public.referral_on_first_payment() to service_role;
grant execute on function public.referral_on_reversal() to service_role;
grant execute on function public.referral_summary(uuid) to service_role;
grant execute on function public.billing_grant_pack(jsonb) to service_role;
