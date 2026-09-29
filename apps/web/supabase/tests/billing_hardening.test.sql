-- pgTAP: billing hardening (migration 20260929210000_billing_hardening.sql): security review L1, L3, L9, L11.
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(42);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at)
values ('c1111111-1111-1111-1111-111111111111', 'harden-a@example.com', now()),
       ('c2222222-2222-2222-2222-222222222222', 'harden-b@example.com', now()),
       ('c3333333-3333-3333-3333-333333333333', 'harden-c@example.com', now()),
       ('c4444444-4444-4444-4444-444444444444', 'harden-admin@example.com', now());
reset role;
insert into public.admins (user_id, note) values ('c4444444-4444-4444-4444-444444444444', 'test');

-- ---------------------------------------------------------------------------------------------
-- L1: nothing unpaid grants credits or a plan, unless it is an allowlisted promo.
-- ---------------------------------------------------------------------------------------------
select is(public.billing_apply_event('evt_h01', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"c1111111-1111-1111-1111-111111111111","transaction_id":"txn_free1",
    "credits":500,"total_minor":0,"paid_minor":0,"currency_code":"USD"}') ->> 'outcome',
  'ignored', 'a 100% discounted pack grants nothing');
select is(public.user_balance('c1111111-1111-1111-1111-111111111111'), 10, 'balance is still just the signup grant');
select is((select count(*)::int from public.billing_transactions where id = 'txn_free1'), 0, 'no transaction recorded for it');
select is((select outcome from public.billing_events where event_id = 'evt_h01'), 'ignored', 'the event is recorded as ignored (no retry)');
select is(public.billing_apply_event('evt_h02', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"c1111111-1111-1111-1111-111111111111","transaction_id":"txn_free2",
    "credits":100,"total_minor":0,"paid_minor":0,"promo":true}') ->> 'outcome',
  'granted', 'an allowlisted promo pack at $0 grants');
select is(public.billing_apply_event('evt_h03', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"c1111111-1111-1111-1111-111111111111","transaction_id":"txn_credit1",
    "credits":100,"total_minor":0,"paid_minor":500}') ->> 'outcome',
  'granted', 'a pack paid from the Paddle credit balance (grand total 0, total 500) grants');
select is(public.billing_apply_event('evt_h04', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"c1111111-1111-1111-1111-111111111111","transaction_id":"txn_legacy",
    "credits":100,"total_minor":0}') ->> 'outcome',
  'ignored', 'an action without paid_minor falls back to total_minor');
select is(public.user_balance('c1111111-1111-1111-1111-111111111111'), 210, '10 + promo 100 + credit-balance 100');

-- A trial: the subscription is trialing, its first period cost nothing.
select is(public.billing_apply_event('evt_h10', 'subscription.created', now(),
  format('{"kind":"subscription_state","user_id":"c2222222-2222-2222-2222-222222222222","subscription_id":"sub_trial",
    "plan":"pro","price_id":"pri_p","status":"trialing","period_start":"%s","period_end":"%s","updated_at":"%s"}',
    now() - interval '1 day', now() + interval '13 days', now())::jsonb) ->> 'outcome',
  'synced', 'a trialing subscription is stored');
select is(public.user_plan('c2222222-2222-2222-2222-222222222222'), 'free'::public.plan_tier, 'a trial grants no plan features');
select is((select max_resolution from public.user_plan_limits('c2222222-2222-2222-2222-222222222222')),
          (select max_resolution from public.plan_limits('free')), 'trial render limits are Free''s');
select is(public.billing_apply_event('evt_h11', 'transaction.completed', now(),
  format('{"kind":"grant_subscription","user_id":"c2222222-2222-2222-2222-222222222222","transaction_id":"txn_trial0",
    "subscription_id":"sub_trial","plan":"pro","credits":2000,"period_start":"%s","period_end":"%s","total_minor":0,"paid_minor":0}',
    now() - interval '1 day', now() + interval '13 days')::jsonb) ->> 'outcome',
  'ignored', 'the $0 trial period grants nothing');
select is(public.user_plan('c2222222-2222-2222-2222-222222222222'), 'free'::public.plan_tier, 'still Free after the $0 transaction');
select is((select plan from public.profiles where id = 'c2222222-2222-2222-2222-222222222222'), 'free'::public.plan_tier, 'profile shows Free');
-- First paid period.
select is((public.billing_apply_event('evt_h12', 'transaction.completed', now(),
  format('{"kind":"grant_subscription","user_id":"c2222222-2222-2222-2222-222222222222","transaction_id":"txn_trial1",
    "subscription_id":"sub_trial","plan":"pro","credits":2000,"period_start":"%s","period_end":"%s","total_minor":4900,"paid_minor":4900}',
    now() + interval '13 days', now() + interval '43 days')::jsonb) ->> 'credits')::int,
  2000, 'the first paid period grants the plan credits');
select is(public.user_plan('c2222222-2222-2222-2222-222222222222'), 'pro'::public.plan_tier, 'and the plan');
select is(public.billing_apply_event('evt_h13', 'transaction.completed', now(),
  format('{"kind":"grant_subscription","transaction_id":"txn_trial2","subscription_id":"sub_trial","plan":"pro",
    "credits":2000,"period_start":"%s","period_end":"%s","total_minor":0,"paid_minor":0}',
    now() + interval '43 days', now() + interval '73 days')::jsonb) ->> 'outcome',
  'ignored', 'a $0 renewal (100% recurring discount) grants nothing either');

-- ---------------------------------------------------------------------------------------------
-- L11: an upgrade top-up is scaled from billed_at, not from when the webhook ran.
-- ---------------------------------------------------------------------------------------------
select public.billing_apply_event('evt_h20', 'transaction.completed', now(),
  '{"kind":"grant_subscription","user_id":"c3333333-3333-3333-3333-333333333333","transaction_id":"txn_c1",
    "subscription_id":"sub_c","plan":"creator","credits":500,"period_start":"2099-01-01T00:00:00Z",
    "period_end":"2099-01-31T00:00:00Z","total_minor":1900,"paid_minor":1900}');
select is((public.billing_apply_event('evt_h21', 'transaction.completed', now(),
  '{"kind":"grant_subscription","transaction_id":"txn_c2","subscription_id":"sub_c","plan":"pro","credits":2000,
    "period_start":"2099-01-08T12:00:00Z","period_end":"2099-01-31T00:00:00Z","billed_at":"2099-01-08T12:00:00Z",
    "total_minor":2200,"paid_minor":2200}') ->> 'credits')::int,
  1125, 'an upgrade billed a quarter into the period tops up 3/4 of the difference');

-- ---------------------------------------------------------------------------------------------
-- L9: reversals that cannot apply are held (200), and applied if their payment arrives later.
-- ---------------------------------------------------------------------------------------------
select is(public.billing_apply_event('evt_h30', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_free1","transaction_id":"txn_free1","action":"refund","full":true,"amount_minor":0}') ->> 'outcome',
  'unapplied', 'a refund of a transaction that granted nothing is held, not raised');
select is((select reason from public.billing_unapplied_adjustments where adjustment_id = 'adj_free1'), 'no_transaction', 'held as no_transaction');
select is((select outcome from public.billing_events where event_id = 'evt_h30'), 'unapplied', 'the event id is consumed (Paddle stops retrying)');
-- Out of order: the refund arrives first, then its payment.
select is(public.billing_apply_event('evt_h31', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_late","transaction_id":"txn_late","action":"refund","full":true,"amount_minor":0}') ->> 'outcome',
  'unapplied', 'a refund before its payment is held');
select public.billing_apply_event('evt_h32', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"c1111111-1111-1111-1111-111111111111","transaction_id":"txn_late",
    "credits":100,"total_minor":500,"paid_minor":500}');
select is(public.user_balance('c1111111-1111-1111-1111-111111111111'), 210, 'the held refund is applied when the payment lands (net 0)');
select is((select resolved_outcome from public.billing_unapplied_adjustments where adjustment_id = 'adj_late'), 'reversed', 'and marked resolved');
select is((select credits from public.billing_adjustments where id = 'adj_late'), -100, 'recorded as a normal adjustment');

-- ---------------------------------------------------------------------------------------------
-- L3: deleting an account keeps its financial rows (user_id -> null); reversals for it are held.
-- ---------------------------------------------------------------------------------------------
select is((select count(*)::int from public.credit_ledger where user_id = 'c3333333-3333-3333-3333-333333333333'), 3,
          'C has a signup grant and two plan grants');
set local role supabase_auth_admin;
delete from auth.users where id = 'c3333333-3333-3333-3333-333333333333';
reset role;
select is((select count(*)::int from public.credit_ledger where ref in ('signup:c3333333-3333-3333-3333-333333333333')
           or ref like 'paddle:sub:sub_c:%'), 3, 'account deletion keeps the ledger rows');
select is((select count(*)::int from public.credit_ledger where ref like 'paddle:sub:sub_c:%' and user_id is null), 2,
          'detached from the deleted account');
select is((select count(*)::int from public.billing_transactions where id in ('txn_c1', 'txn_c2') and user_id is null), 2,
          'payment records survive, detached');
select is(public.billing_apply_event('evt_h40', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_gone","transaction_id":"txn_c1","action":"chargeback","full":true,"amount_minor":0}') ->> 'outcome',
  'unapplied', 'a chargeback for a deleted account is held, not raised');
select is((select reason from public.billing_unapplied_adjustments where adjustment_id = 'adj_gone'), 'account_deleted', 'held as account_deleted');
select throws_ok($$ update public.credit_ledger set user_id = 'c1111111-1111-1111-1111-111111111111' where ref like 'paddle:sub:sub_c:%' $$,
  '42501', null, 'a detached ledger row cannot be re-assigned to another user');

-- Append-only, even for the table owner (triggers) ...
select throws_ok($$ delete from public.credit_ledger where ref = 'paddle:txn:txn_late' $$, '42501', null, 'owner cannot delete ledger rows');
select throws_ok($$ truncate public.credit_ledger cascade $$, '42501', null, 'owner cannot truncate the ledger');
select throws_ok($$ truncate public.admin_audit_log $$, '42501', null, 'owner cannot truncate the audit log');
select throws_ok($$ delete from public.billing_events where event_id = 'evt_h01' $$, '42501', null, 'owner cannot delete billing events');

-- ... and for the service role (privileges), which still does its normal work.
set local role service_role;
select throws_ok($$ delete from public.credit_ledger where ref = 'paddle:txn:txn_late' $$, '42501', null, 'service role cannot delete ledger rows');
select throws_ok($$ update public.admin_audit_log set reason = 'x' $$, '42501', null, 'service role cannot edit the audit log');
select throws_ok($$ delete from public.billing_transactions where id = 'txn_late' $$, '42501', null, 'service role cannot delete transactions');
select is(public.billing_apply_event('evt_h49', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"c1111111-1111-1111-1111-111111111111","transaction_id":"txn_sr",
    "credits":100,"total_minor":500,"paid_minor":500}') ->> 'outcome', 'granted', 'the service role still grants packs');
select is(public.billing_apply_event('evt_h50', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_sr","transaction_id":"txn_sr","action":"refund","full":false,"amount_minor":250}') ->> 'credits',
  '-50', 'the service role still applies refunds (updates credits_reversed, event outcome)');
select is((public.admin_adjust_credits('c4444444-4444-4444-4444-444444444444', 'c1111111-1111-1111-1111-111111111111', 10,
  'goodwill', 'req-harden-0001') ->> 'amount')::int, 10, 'the service role still writes ledger + audit rows');
reset role;

select * from finish();
rollback;
