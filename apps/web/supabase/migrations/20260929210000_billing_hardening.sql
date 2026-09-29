-- Valora3D billing hardening (security review 2026-09-28, lane sec-billing, 2026-09-29).
--
--   L1  A transaction nobody paid for (a 100% discount, a trial's $0 first period) grants nothing: no pack
--       credits, no plan credits, and no plan features. It grants only when lib/billing/events.ts marks it a
--       promo (its price is on PADDLE_PROMO_PRICE_IDS, empty by default). user_plan() now also requires a
--       period that was actually paid (paid_through set), so a trialing / $0 subscription is Free until its
--       first paid transaction, the same rule the credits already followed.
--   L3  Financial and audit tables are append-only for the service role too: no DELETE / TRUNCATE (and no
--       UPDATE where nothing legitimately updates), backed by triggers that also stop the table owner.
--       Deleting an account no longer deletes its ledger or payment records: their user_id is set to NULL
--       (ON DELETE SET NULL). What stays is amounts, reasons, timestamps and Paddle ids, no email or name:
--       bookkeeping records kept under the legal obligation to keep accounting records (GDPR art. 17(3)(b)),
--       detached from the erased account. Paddle, the merchant of record, keeps its own copy anyway.
--   L9  A refund / chargeback for a transaction that never granted anything, or whose account was deleted,
--       no longer raises (Paddle would retry it for days). It is held in billing_unapplied_adjustments
--       (shown on /admin/billing) and the webhook answers 200. If the payment it belongs to is applied later
--       (Paddle does not order deliveries), the held reversal is applied at that moment.
--   L11 An upgrade's top-up is scaled from the transaction's own billed_at (sent by the webhook), not from the
--       time the webhook happened to be processed, so a late or retried delivery grants what was charged.
--
-- Rules from earlier migrations hold: RLS on every table, no SECURITY DEFINER, search_path ''. The billing
-- functions below keep their signatures, so `create or replace` keeps their service-role-only grants.

-- ---------------------------------------------------------------------------------------------
-- L3: keep financial rows when an account is deleted.
-- ---------------------------------------------------------------------------------------------

alter table public.credit_ledger alter column user_id drop not null;
alter table public.credit_ledger drop constraint credit_ledger_user_id_fkey;
alter table public.credit_ledger add constraint credit_ledger_user_id_fkey
  foreign key (user_id) references auth.users (id) on delete set null;

alter table public.billing_transactions alter column user_id drop not null;
alter table public.billing_transactions drop constraint billing_transactions_user_id_fkey;
alter table public.billing_transactions add constraint billing_transactions_user_id_fkey
  foreign key (user_id) references auth.users (id) on delete set null;

alter table public.billing_adjustments alter column user_id drop not null;
alter table public.billing_adjustments drop constraint billing_adjustments_user_id_fkey;
alter table public.billing_adjustments add constraint billing_adjustments_user_id_fkey
  foreign key (user_id) references auth.users (id) on delete set null;

-- The ledger's one allowed update was "a parent FK column set to null"; the owner column is now one of them
-- (only ever to NULL, only by the account-deletion cascade in practice).
create or replace function public.credit_ledger_block_update() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if (new.user_id is distinct from old.user_id and new.user_id is not null)
     or new.amount is distinct from old.amount
     or new.reason is distinct from old.reason
     or new.ref is distinct from old.ref
     or new.created_at is distinct from old.created_at then
    raise exception 'credit_ledger is append-only' using errcode = '42501';
  end if;
  return new;
end $$;

-- One trigger function for "this table keeps its rows": row DELETE and statement TRUNCATE (a TRUNCATE skips
-- row triggers, so it needs its own).
create or replace function public.block_append_only_delete() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception '% is append-only', tg_table_name using errcode = '42501';
end $$;
revoke all on function public.block_append_only_delete() from public, anon, authenticated;

create trigger credit_ledger_no_delete before delete on public.credit_ledger
  for each row execute function public.block_append_only_delete();
create trigger credit_ledger_no_truncate before truncate on public.credit_ledger
  for each statement execute function public.block_append_only_delete();
create trigger admin_audit_log_no_truncate before truncate on public.admin_audit_log
  for each statement execute function public.block_append_only_delete();
create trigger billing_events_no_delete before delete on public.billing_events
  for each row execute function public.block_append_only_delete();
create trigger billing_events_no_truncate before truncate on public.billing_events
  for each statement execute function public.block_append_only_delete();
create trigger billing_transactions_no_delete before delete on public.billing_transactions
  for each row execute function public.block_append_only_delete();
create trigger billing_transactions_no_truncate before truncate on public.billing_transactions
  for each statement execute function public.block_append_only_delete();
create trigger billing_adjustments_no_delete before delete on public.billing_adjustments
  for each row execute function public.block_append_only_delete();
create trigger billing_adjustments_no_truncate before truncate on public.billing_adjustments
  for each statement execute function public.block_append_only_delete();

-- Privileges. UPDATE stays where the app updates rows: billing_events.outcome (billing_apply_event) and
-- billing_transactions.credits_reversed (billing_reverse). Referential actions (SET NULL) run as the table
-- owner, so they need none of these grants.
revoke update, delete, truncate on public.credit_ledger from service_role;
revoke update, delete, truncate on public.admin_audit_log from service_role;
revoke update, delete, truncate on public.billing_adjustments from service_role;
revoke delete, truncate on public.billing_events from service_role;
revoke delete, truncate on public.billing_transactions from service_role;

-- ---------------------------------------------------------------------------------------------
-- L9: reversals we cannot apply are held, not retried forever.
-- ---------------------------------------------------------------------------------------------

create table public.billing_unapplied_adjustments (
  adjustment_id    text primary key check (adjustment_id ~ '^adj_[a-z0-9]+$'),
  transaction_id   text not null check (char_length(transaction_id) <= 64),
  action           text not null check (action in ('refund', 'credit', 'chargeback', 'chargeback_reverse')),
  -- no_transaction: nothing was ever granted for that transaction (yet). account_deleted: it was, but the
  -- account is gone, so there is nobody to take the credits back from.
  reason           text not null check (reason in ('no_transaction', 'account_deleted')),
  -- The reversal action exactly as the webhook sent it (amounts and Paddle ids only), replayed if the payment
  -- is applied later.
  payload          jsonb not null,
  received_at      timestamptz not null default now(),
  resolved_at      timestamptz,
  resolved_outcome text check (resolved_outcome is null or char_length(resolved_outcome) <= 32)
);
create index billing_unapplied_adjustments_txn_idx on public.billing_unapplied_adjustments (transaction_id)
  where resolved_at is null;
create index billing_unapplied_adjustments_received_idx on public.billing_unapplied_adjustments (received_at desc);

alter table public.billing_unapplied_adjustments enable row level security;
revoke all on public.billing_unapplied_adjustments from anon, authenticated;
grant select, insert, update on public.billing_unapplied_adjustments to service_role;
-- No policies: service role only (the webhook writes it, /admin reads it).

-- ---------------------------------------------------------------------------------------------
-- L1: the effective plan needs a paid period.
-- ---------------------------------------------------------------------------------------------

-- The plan a user is entitled to right now: the best subscription that has had at least one PAID period
-- (paid_through set by billing_grant_subscription) and is either still active/trialing or inside that paid
-- period, unless the period's payment was refunded or charged back. Otherwise Free. A subscription whose
-- first period cost nothing (a trial, a 100% discount) is Free until a period is paid, like its credits.
create or replace function public.user_plan(p_user_id uuid) returns public.plan_tier
language sql stable
set search_path = ''
as $$
  select coalesce(
    (select s.plan from public.billing_subscriptions s
      where s.user_id = p_user_id
        and s.paid_through is not null
        and (s.status in ('active', 'trialing') or s.paid_through > now())
        and (s.revoked_through is null or s.revoked_through <= now())
      order by s.plan desc
      limit 1),
    'free'::public.plan_tier)
$$;

-- True when a grant action carries a real charge, or is an allowlisted promo. `paid_minor` is the
-- transaction total after discounts and before any Paddle account credit was applied (so a renewal paid from
-- the customer's credit balance still counts as paid); older callers send only total_minor.
create or replace function public.billing_action_paid(p_action jsonb) returns boolean
language sql immutable
set search_path = ''
as $$
  select coalesce((p_action ->> 'paid_minor')::bigint, (p_action ->> 'total_minor')::bigint, 0) > 0
      or coalesce((p_action ->> 'promo')::boolean, false)
$$;
revoke all on function public.billing_action_paid(jsonb) from public, anon, authenticated;
grant execute on function public.billing_action_paid(jsonb) to service_role;

-- Applies any reversal held for p_txn (it arrived before its payment). Called by the grant functions right
-- after they record the transaction, in the same transaction.
create or replace function public.billing_apply_held_adjustments(p_txn text) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_row    public.billing_unapplied_adjustments;
  v_result jsonb;
  v_count  integer := 0;
begin
  for v_row in
    select * from public.billing_unapplied_adjustments
     where transaction_id = p_txn and resolved_at is null and reason = 'no_transaction'
     order by received_at
     for update
  loop
    v_result := public.billing_reverse(v_row.payload);
    update public.billing_unapplied_adjustments
       set resolved_at = now(), resolved_outcome = left(v_result ->> 'outcome', 32)
     where adjustment_id = v_row.adjustment_id;
    v_count := v_count + 1;
  end loop;
  return v_count;
end $$;
revoke all on function public.billing_apply_held_adjustments(text) from public, anon, authenticated;
grant execute on function public.billing_apply_held_adjustments(text) to service_role;

-- ---------------------------------------------------------------------------------------------
-- Grants (L1 + L9 + L11)
-- ---------------------------------------------------------------------------------------------

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
  perform public.billing_apply_held_adjustments(v_txn);
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
  -- L11: when Paddle billed this transaction (the webhook sends billed_at, else the event time).
  v_billed     timestamptz := coalesce((p_action ->> 'billed_at')::timestamptz, now());
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
  -- L1: a period nobody paid for grants neither credits nor the plan (paid_through stays as it was).
  if not public.billing_action_paid(p_action) then
    return jsonb_build_object('outcome', 'ignored', 'detail', 'unpaid period ' || v_txn);
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
  -- ends with the same period) tops up the difference scaled by the share of the period left at the
  -- moment Paddle billed it, the same share Paddle charges for. Downgrades are not billed.
  select coalesce(sum(credits_granted), 0)::integer, min(period_start) into v_already, v_first
    from public.billing_transactions
   where subscription_id = v_sub and period_end = v_end;
  if v_already = 0 then
    v_amount := v_credits;
  else
    v_fraction := case
      when v_first is null or v_end <= v_first then 1
      else greatest(0, least(1, extract(epoch from (v_end - greatest(v_billed, v_first)))
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

  insert into public.billing_transactions
    (id, user_id, kind, subscription_id, customer_id, plan, credits_granted, total_minor, currency_code, period_start, period_end)
  values (v_txn, v_user, 'subscription', v_sub, p_action ->> 'customer_id', v_plan, v_amount,
          coalesce((p_action ->> 'total_minor')::bigint, 0), p_action ->> 'currency_code', v_start, v_end);

  insert into public.billing_subscriptions (id, user_id, customer_id, plan, status, current_period_start, current_period_end, paid_through)
  values (v_sub, v_user, p_action ->> 'customer_id', v_plan, 'active', v_start, v_end, v_end)
  on conflict (id) do update
    set paid_through = greatest(coalesce(public.billing_subscriptions.paid_through, excluded.paid_through), excluded.paid_through);

  perform public.billing_apply_held_adjustments(v_txn);
  perform public.sync_profile_plan(v_user);
  return jsonb_build_object('outcome', 'granted', 'user_id', v_user, 'credits', v_amount);
end $$;

-- ---------------------------------------------------------------------------------------------
-- Reversals (L9)
-- ---------------------------------------------------------------------------------------------

create or replace function public.billing_hold_adjustment(p_action jsonb, p_reason text) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_adj text := p_action ->> 'adjustment_id';
begin
  insert into public.billing_unapplied_adjustments (adjustment_id, transaction_id, action, reason, payload)
  values (v_adj, left(coalesce(p_action ->> 'transaction_id', '?'), 64), p_action ->> 'action', p_reason, p_action)
  on conflict (adjustment_id) do nothing;
  return jsonb_build_object('outcome', 'unapplied', 'detail', p_reason || ': ' || v_adj);
end $$;
revoke all on function public.billing_hold_adjustment(jsonb, text) from public, anon, authenticated;
grant execute on function public.billing_hold_adjustment(jsonb, text) to service_role;

-- Refund / credit / chargeback: take back the credits that transaction granted, in proportion to the
-- amount adjusted (a full adjustment takes back everything still outstanding). A reversed
-- chargeback gives them back. The balance may go negative. A reversal with no granted transaction, or whose
-- account was deleted, is held (outcome 'unapplied') instead of raising.
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
  if v_adj is null or v_adj !~ '^adj_[a-z0-9]+$' or v_kind is null
     or v_kind not in ('refund', 'credit', 'chargeback', 'chargeback_reverse') then
    raise exception 'bad reversal' using errcode = '22023';
  end if;
  select * into v_txn from public.billing_transactions where id = p_action ->> 'transaction_id' for update;
  if not found then
    -- Never granted: a $0 / ignored transaction, or its payment has not been applied yet (then the grant
    -- applies this hold when it arrives).
    return public.billing_hold_adjustment(p_action, 'no_transaction');
  end if;
  if exists (select 1 from public.billing_adjustments where id = v_adj) then
    return jsonb_build_object('outcome', 'duplicate_txn', 'detail', v_adj);
  end if;
  if v_txn.user_id is null then
    return public.billing_hold_adjustment(p_action, 'account_deleted');
  end if;

  perform public.lock_user_credits(v_txn.user_id);
  v_share := case
    when v_full or v_txn.total_minor <= 0 then v_txn.credits_granted
    else least(v_txn.credits_granted, ceil(v_txn.credits_granted::numeric * v_amount / v_txn.total_minor)::integer)
  end;

  if v_kind = 'chargeback_reverse' then
    v_delta := least(v_share, v_txn.credits_reversed);
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
