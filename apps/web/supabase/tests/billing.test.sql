-- pgTAP: Paddle billing -> ledger, plans, idempotency (migration 20260928130000_billing.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(43);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at)
values ('11111111-1111-1111-1111-111111111111', 'pay-a@example.com', now()),
       ('22222222-2222-2222-2222-222222222222', 'pay-b@example.com', now());
reset role;

-- Plan limits (mirrored by PLAN_LIMITS in lib/pricing.ts).
select is((select max_resolution from public.plan_limits('free')), '540p', 'free renders 540p previews');
select is((select watermark from public.plan_limits('free')), true, 'free is watermarked');
select is((select max_resolution || '/' || retention_days || '/' || max_active_jobs from public.plan_limits('pro')), '1080p/90/3', 'pro limits');
select is(public.user_plan('11111111-1111-1111-1111-111111111111'), 'free'::public.plan_tier, 'a new user is on Free');
select is((select max_resolution from public.user_plan_limits('11111111-1111-1111-1111-111111111111')), '540p',
          'user_plan_limits follows the effective plan');

-- Pack purchase: granted once per event and once per transaction.
select is(public.billing_apply_event('evt_01', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"11111111-1111-1111-1111-111111111111","customer_id":"ctm_a",
    "transaction_id":"txn_pack1","credits":100,"total_minor":500,"currency_code":"USD"}') ->> 'outcome',
  'granted', 'a pack purchase grants credits');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 150, 'balance = signup 50 + pack 100');
select is(public.billing_apply_event('evt_01', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"11111111-1111-1111-1111-111111111111","customer_id":"ctm_a",
    "transaction_id":"txn_pack1","credits":100,"total_minor":500,"currency_code":"USD"}') ->> 'outcome',
  'duplicate', 'a replayed event id does nothing');
select is(public.billing_apply_event('evt_02', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"11111111-1111-1111-1111-111111111111","customer_id":"ctm_a",
    "transaction_id":"txn_pack1","credits":100,"total_minor":500,"currency_code":"USD"}') ->> 'outcome',
  'duplicate_txn', 'the same transaction under a new event id does nothing');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 150, 'still granted once');
select is((select count(*)::int from public.credit_ledger where ref = 'paddle:txn:txn_pack1'), 1, 'one ledger row, ref = transaction id');
select is((select count(*)::int from public.billing_customers), 0, 'webhooks never link a Paddle customer');
select public.billing_link_customer('11111111-1111-1111-1111-111111111111', 'ctm_a');
select is((select paddle_customer_id from public.billing_customers where user_id = '11111111-1111-1111-1111-111111111111'),
          'ctm_a', 'checkout links the customer found for the account''s own email');

-- Subscription: state event, then the first payment, a renewal and an upgrade inside a period.
select is(public.billing_apply_event('evt_03', 'subscription.created', now(),
  '{"kind":"subscription_state","user_id":"11111111-1111-1111-1111-111111111111","customer_id":"ctm_a",
    "subscription_id":"sub_1","plan":"creator","price_id":"pri_c","status":"active",
    "period_start":"2026-09-01T00:00:00Z","period_end":"2026-10-01T00:00:00Z","updated_at":"2026-09-01T00:00:01Z"}') ->> 'outcome',
  'synced', 'subscription.created is stored');
select is((select plan from public.profiles where id = '11111111-1111-1111-1111-111111111111'), 'free'::public.plan_tier,
          'a subscription with no paid period yet grants no plan (billing_hardening L1)');
select is(public.billing_apply_event('evt_04', 'transaction.completed', now(),
  '{"kind":"grant_subscription","customer_id":"ctm_a","transaction_id":"txn_s1","subscription_id":"sub_1",
    "plan":"creator","credits":500,"period_start":"2026-09-01T00:00:00Z","period_end":"2026-10-01T00:00:00Z",
    "total_minor":1900,"currency_code":"USD"}') ->> 'credits',
  '500', 'the first period grants the plan credits (user resolved from the subscription)');
select is(public.billing_apply_event('evt_05', 'transaction.completed', now(),
  '{"kind":"grant_subscription","customer_id":"ctm_a","transaction_id":"txn_s2","subscription_id":"sub_1",
    "plan":"creator","credits":500,"period_start":"2026-10-01T00:00:00Z","period_end":"2099-11-01T00:00:00Z",
    "total_minor":1900,"currency_code":"USD"}') ->> 'credits',
  '500', 'a renewal grants again for the new period');
select is(public.billing_apply_event('evt_06', 'transaction.completed', now(),
  '{"kind":"grant_subscription","customer_id":"ctm_a","transaction_id":"txn_s3","subscription_id":"sub_1",
    "plan":"pro","credits":2000,"period_start":"2026-10-15T00:00:00Z","period_end":"2099-11-01T00:00:00Z",
    "total_minor":1500,"currency_code":"USD"}') ->> 'credits',
  '1500', 'an upgrade inside a period tops up to the new plan');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 2650, '150 + 500 + 500 + 1500');

-- Out-of-order events: an older subscription.updated is ignored.
select is(public.billing_apply_event('evt_07', 'subscription.updated', now(),
  '{"kind":"subscription_state","customer_id":"ctm_a","subscription_id":"sub_1","plan":"pro","price_id":"pri_p",
    "status":"active","period_start":"2026-10-01T00:00:00Z","period_end":"2099-11-01T00:00:00Z",
    "updated_at":"2026-10-15T00:00:00Z"}') ->> 'outcome', 'synced', 'the upgrade event is stored');
select is(public.billing_apply_event('evt_08', 'subscription.updated', now(),
  '{"kind":"subscription_state","customer_id":"ctm_a","subscription_id":"sub_1","plan":"creator","price_id":"pri_c",
    "status":"active","period_start":"2026-09-01T00:00:00Z","period_end":"2026-10-01T00:00:00Z",
    "updated_at":"2026-09-02T00:00:00Z"}') ->> 'outcome', 'stale', 'an older event is ignored');
select is(public.user_plan('11111111-1111-1111-1111-111111111111'), 'pro'::public.plan_tier, 'the plan is Pro');

-- Canceled keeps the plan until the paid period ends, then Free.
select is(public.billing_apply_event('evt_09', 'subscription.canceled', now(),
  '{"kind":"subscription_state","customer_id":"ctm_a","subscription_id":"sub_1","plan":"pro","price_id":"pri_p",
    "status":"canceled","period_start":"2026-10-01T00:00:00Z","period_end":"2099-11-01T00:00:00Z",
    "updated_at":"2026-10-20T00:00:00Z"}') ->> 'plan', 'pro', 'canceled: still Pro until the paid period ends');
update public.billing_subscriptions set paid_through = now() - interval '1 second' where id = 'sub_1';
select is(public.user_plan('11111111-1111-1111-1111-111111111111'), 'free'::public.plan_tier,
          'after the paid period the plan falls to Free');
select is(public.sync_expired_plans(), 1, 'the scheduled sweep moves the stale profile to Free');

-- Refunds and chargebacks.
select is(public.billing_apply_event('evt_10', 'adjustment.updated', now(),
  '{"kind":"reversal","adjustment_id":"adj_1","transaction_id":"txn_pack1","action":"refund","full":false,"amount_minor":250}') ->> 'credits',
  '-50', 'a half refund takes back half the pack');
select is(public.billing_apply_event('evt_11', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_2","transaction_id":"txn_s3","action":"chargeback","full":true,"amount_minor":0}') ->> 'credits',
  '-1500', 'a chargeback takes back what that transaction granted');
select is(public.billing_apply_event('evt_12', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_2","transaction_id":"txn_s3","action":"chargeback","full":true,"amount_minor":0}') ->> 'outcome',
  'duplicate_txn', 'the same adjustment is applied once');
select is(public.billing_apply_event('evt_13', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_3","transaction_id":"txn_s3","action":"chargeback_reverse","full":true,"amount_minor":0}') ->> 'credits',
  '1500', 'a reversed chargeback gives the credits back');
select is((select count(*)::int from public.credit_ledger where reason = 'billing_reversal'), 3, 'three reversal rows');

-- A reversal may push the balance below zero, which blocks new renders (even free ones).
insert into public.projects (id, user_id, name) values
  ('aaaaaaaa-0000-0000-0000-00000000000b', '22222222-2222-2222-2222-222222222222', 'B car');
select public.billing_apply_event('evt_14', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"22222222-2222-2222-2222-222222222222","customer_id":"ctm_b",
    "transaction_id":"txn_packb","credits":100,"total_minor":500,"currency_code":"USD"}');
select public.spend_credits('22222222-2222-2222-2222-222222222222', 120, 'scene_generation', 'spend:b:1', null);
select public.billing_apply_event('evt_15', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_b","transaction_id":"txn_packb","action":"chargeback","full":true,"amount_minor":0}');
select is(public.user_balance('22222222-2222-2222-2222-222222222222'), -70, 'the balance can go negative');
select throws_ok(
  $$ select public.create_render_job('22222222-2222-2222-2222-222222222222', 'aaaaaaaa-0000-0000-0000-00000000000b',
       null, null, 'preview', '{}', 0, 'negative-balance-key') $$,
  'P0001', null, 'a negative balance blocks new renders, even free ones');

-- Unknown owner: the whole event rolls back (500 -> Paddle retries), nothing is recorded.
select throws_ok($$ select public.billing_apply_event('evt_16', 'transaction.completed', now(),
  '{"kind":"grant_pack","customer_id":"ctm_nobody","transaction_id":"txn_orphan","credits":100,"total_minor":500}') $$,
  'P0002', null, 'a payment with no signed owner fails so Paddle retries');
select is((select count(*)::int from public.billing_events where event_id = 'evt_16'), 0, 'the event id is not consumed');
-- A pack under A's linked Paddle customer but without A's signature is not credited to A.
select throws_ok($$ select public.billing_apply_event('evt_17', 'transaction.completed', now(),
  '{"kind":"grant_pack","customer_id":"ctm_a","transaction_id":"txn_hijack","credits":100,"total_minor":500}') $$,
  'P0002', null, 'the Paddle customer alone never decides whose account is credited');
select is(public.billing_apply_event('evt_18', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_early","transaction_id":"txn_notyet","action":"refund","full":true,"amount_minor":0}') ->> 'outcome',
  'unapplied', 'a refund that arrives before its payment is held, not retried forever (billing_hardening L9)');

-- User B: a late upgrade tops up only the share of the period left; a full chargeback of the
-- plan payment removes the plan, and reversing it restores the plan.
select public.billing_apply_event('evt_20', 'transaction.completed', now(),
  format('{"kind":"grant_subscription","user_id":"22222222-2222-2222-2222-222222222222","transaction_id":"txn_b1","subscription_id":"sub_b",
    "plan":"creator","credits":500,"period_start":"%s","period_end":"%s","total_minor":1900}',
    now() - interval '15 days', now() + interval '15 days')::jsonb);
select is((select plan from public.profiles where id = '22222222-2222-2222-2222-222222222222'), 'creator'::public.plan_tier, 'B is on Creator');
select is((public.billing_apply_event('evt_21', 'transaction.completed', now(),
  format('{"kind":"grant_subscription","transaction_id":"txn_b2","subscription_id":"sub_b",
    "plan":"pro","credits":2000,"period_start":"%s","period_end":"%s","total_minor":750}',
    now(), (select period_end from public.billing_transactions where id = 'txn_b1'))::jsonb) ->> 'credits')::int,
  750, 'an upgrade half way through tops up half the difference');
select is((public.billing_apply_event('evt_22', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_b1","transaction_id":"txn_b1","action":"chargeback","full":true,"amount_minor":0}') ->> 'credits')::int,
  -500, 'a chargeback of the plan payment takes its credits back');
select is(public.user_plan('22222222-2222-2222-2222-222222222222'), 'free'::public.plan_tier, 'and removes the plan for that period');
select public.billing_apply_event('evt_23', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_b2","transaction_id":"txn_b1","action":"chargeback_reverse","full":true,"amount_minor":0}');
select is(public.user_plan('22222222-2222-2222-2222-222222222222'), 'creator'::public.plan_tier, 'a reversed chargeback restores it (the plan itself follows subscription.updated)');

-- Users cannot call the billing functions or read billing_events.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select throws_ok(
  $$ select public.billing_apply_event('evt_99', 'x', now(), '{"kind":"ignore"}') $$,
  '42501', null, 'users cannot apply billing events');
select throws_ok($$ select * from public.billing_events $$, '42501', null, 'users cannot read billing events');
reset role;

select * from finish();
rollback;
