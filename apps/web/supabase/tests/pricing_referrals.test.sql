-- pgTAP: pricing v2, plan-credit rollover and referrals (migration 20260930120000_pricing_referrals.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(50);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at)
values ('f1000000-0000-0000-0000-000000000001', 'ref-owner@example.com', now()),
       ('f2000000-0000-0000-0000-000000000002', 'ref-friend@example.com', now()),
       ('f3000000-0000-0000-0000-000000000003', 'Ref-Owner+alt@example.com', now()),
       ('f4000000-0000-0000-0000-000000000004', 'ref-sharedcard@example.com', now()),
       ('f5000000-0000-0000-0000-000000000005', 'ref-late@example.com', now()),
       ('f6000000-0000-0000-0000-000000000006', 'plan-user@example.com', now()),
       ('f7000000-0000-0000-0000-000000000007', 'ref-nopay@example.com', now());
insert into auth.users (id, email, email_confirmed_at)
select ('f9000000-0000-0000-0000-' || lpad(g::text, 12, '0'))::uuid, 'cap' || g || '@example.com', now()
  from generate_series(1, 20) g;
reset role;

-- ---------------------------------------------------------------------------------------------
-- Constants (mirrored by lib/pricing.ts; lib/pricing.test.ts pins the text of each)
-- ---------------------------------------------------------------------------------------------
select is(public.free_plan_credits(), 30, 'the Free plan grants 30 credits');
select is(public.user_balance('f1000000-0000-0000-0000-000000000001'), 30, 'a confirmed signup starts with 30 credits');
select is(public.render_cost('preview'), 10, 'a Preview costs 10');
select is(public.render_cost('final'), 200, 'a Final costs 200');
select is(public.render_failure_fee(), public.render_cost('preview'), 'the input-failure fee is the Preview price');
select is(public.plan_credit_rollover(), interval '1 month', 'plan credits roll over one month');
select is(public.referral_bonus_credits(), 100, 'referral bonus is 100');
select is(public.referral_monthly_cap(), 20, 'at most 20 rewarded referrals a month');

-- ---------------------------------------------------------------------------------------------
-- Render prices are enforced on the row
-- ---------------------------------------------------------------------------------------------
insert into public.projects (id, user_id, name) values ('f1a00000-0000-0000-0000-000000000001', 'f1000000-0000-0000-0000-000000000001', 'P');
select throws_ok($$ insert into public.render_jobs (user_id, project_id, kind, cost_credits)
                    values ('f1000000-0000-0000-0000-000000000001', 'f1a00000-0000-0000-0000-000000000001', 'preview', 3) $$,
                 '22023', null, 'a Preview at the old price is refused');
select throws_ok($$ insert into public.render_jobs (user_id, project_id, kind, cost_credits)
                    values ('f1000000-0000-0000-0000-000000000001', 'f1a00000-0000-0000-0000-000000000001', 'final', 10) $$,
                 '22023', null, 'a Final at the Preview price is refused');
select lives_ok($$ insert into public.render_jobs (user_id, project_id, kind, cost_credits, status)
                   values ('f1000000-0000-0000-0000-000000000001', 'f1a00000-0000-0000-0000-000000000001', 'final', 0, 'succeeded') $$,
                'a free (comp) job is allowed');
select throws_ok($$ update public.render_jobs set fee_credits = 11 where user_id = 'f1000000-0000-0000-0000-000000000001' $$,
                 '22023', null, 'a fee above render_failure_fee() is refused');

-- ---------------------------------------------------------------------------------------------
-- Referral codes and joining
-- ---------------------------------------------------------------------------------------------
set local role service_role;
select matches(public.referral_code('f1000000-0000-0000-0000-000000000001'), '^[a-z0-9]{10}$', 'a code is 10 lowercase letters/digits');
select is(public.referral_code('f1000000-0000-0000-0000-000000000001'),
          (select code from public.referral_codes where user_id = 'f1000000-0000-0000-0000-000000000001'), 'the same code on every ask');
select is(public.referral_referrer('u_' || public.referral_code('f1000000-0000-0000-0000-000000000001')),
          'f1000000-0000-0000-0000-000000000001'::uuid, 'u_<code> resolves to its owner');
select is(public.referral_referrer('share_abc'), null, 'a share ref is not a referral');

select ok(public.record_signup_source('f2000000-0000-0000-0000-000000000002',
          jsonb_build_object('ref', 'u_' || public.referral_code('f1000000-0000-0000-0000-000000000001'))), 'friend signs up through the link');
select is((select status from public.referrals where referee_id = 'f2000000-0000-0000-0000-000000000002'), 'joined', 'the friend joined');
select is(public.user_balance('f2000000-0000-0000-0000-000000000002'), 30, 'joining pays nothing (only a payment does)');
select ok(public.record_signup_source('f3000000-0000-0000-0000-000000000003',
          jsonb_build_object('ref', 'u_' || public.referral_code('f1000000-0000-0000-0000-000000000001'))), 'the owner''s +alias signs up through it');
select is((select count(*)::int from public.referrals where referee_id = 'f3000000-0000-0000-0000-000000000003'), 0,
          'the same normalised email never joins (self-referral)');
select is(public.referral_summary('f1000000-0000-0000-0000-000000000001') ->> 'joined', '1', 'summary: 1 joined');
select is(public.referral_summary('f1000000-0000-0000-0000-000000000001') ->> 'qualified', '0', 'summary: 0 qualified');

-- ---------------------------------------------------------------------------------------------
-- First payment pays both, once
-- ---------------------------------------------------------------------------------------------
select is(public.billing_apply_event('evt_ref01', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"f2000000-0000-0000-0000-000000000002","customer_id":"ctm_friend",
    "transaction_id":"txn_ref1","credits":250,"total_minor":1200,"currency_code":"USD"}') ->> 'outcome',
  'granted', 'the friend buys a pack');
select is(public.user_balance('f2000000-0000-0000-0000-000000000002'), 380, 'friend: 30 + 250 + 100 bonus');
select is(public.user_balance('f1000000-0000-0000-0000-000000000001'), 130, 'owner: 30 + 100 bonus');
select is((select status || '/' || referrer_rewarded::text from public.referrals where referee_id = 'f2000000-0000-0000-0000-000000000002'),
          'qualified/true', 'the referral qualified and the referrer was rewarded');
select is(public.billing_apply_event('evt_ref02', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"f2000000-0000-0000-0000-000000000002","customer_id":"ctm_friend",
    "transaction_id":"txn_ref2","credits":250,"total_minor":1200,"currency_code":"USD"}') ->> 'outcome',
  'granted', 'a second purchase');
select is((select count(*)::int from public.credit_ledger where reason = 'referral_bonus'), 2, 'the second purchase pays no bonus');
select is(public.referral_summary('f1000000-0000-0000-0000-000000000001') ->> 'credits_earned', '100', 'summary: 100 earned');

-- A full refund of the qualifying payment takes both bonuses back.
select is(public.billing_apply_event('evt_ref03', 'adjustment.created', now(),
  '{"kind":"reversal","adjustment_id":"adj_ref1","transaction_id":"txn_ref1","action":"refund","full":true}') ->> 'outcome',
  'reversed', 'the qualifying payment is refunded in full');
select is(public.user_balance('f2000000-0000-0000-0000-000000000002'), 280, 'friend: 630 - 250 refunded - 100 bonus');
select is(public.user_balance('f1000000-0000-0000-0000-000000000001'), 30, 'owner: the bonus is taken back');
select is((select status from public.referrals where referee_id = 'f2000000-0000-0000-0000-000000000002'), 'reversed', 'status reversed');

-- The referrer's own Paddle customer paying for the "friend" is a self-referral.
select public.billing_link_customer('f1000000-0000-0000-0000-000000000001', 'ctm_owner');
select public.record_signup_source('f4000000-0000-0000-0000-000000000004',
       jsonb_build_object('ref', 'u_' || public.referral_code('f1000000-0000-0000-0000-000000000001')));
select is(public.billing_apply_event('evt_ref04', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"f4000000-0000-0000-0000-000000000004","customer_id":"ctm_owner",
    "transaction_id":"txn_ref4","credits":250,"total_minor":1200,"currency_code":"USD"}') ->> 'outcome',
  'granted', 'a pack paid with the owner''s Paddle customer');
select is((select status from public.referrals where referee_id = 'f4000000-0000-0000-0000-000000000004'), 'rejected',
          'the same Paddle customer is a self-referral');
select is(public.user_balance('f4000000-0000-0000-0000-000000000004'), 280, 'no bonus: 30 + 250');

-- The monthly cap: 20 already rewarded this month, the next friend still gets theirs, the referrer does not.
reset role;
insert into public.referrals (referee_id, referrer_id, status, qualified_at, referrer_rewarded)
select ('f9000000-0000-0000-0000-' || lpad(g::text, 12, '0'))::uuid, 'f1000000-0000-0000-0000-000000000001', 'qualified', now(), true
  from generate_series(1, 20) g;
set local role service_role;
select public.record_signup_source('f5000000-0000-0000-0000-000000000005',
       jsonb_build_object('ref', 'u_' || public.referral_code('f1000000-0000-0000-0000-000000000001')));
select is(public.billing_apply_event('evt_ref05', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"f5000000-0000-0000-0000-000000000005","customer_id":"ctm_late",
    "transaction_id":"txn_ref5","credits":250,"total_minor":1200,"currency_code":"USD"}') ->> 'outcome',
  'granted', 'the 22nd friend pays');
select is(public.user_balance('f5000000-0000-0000-0000-000000000005'), 380, 'the friend still gets the bonus');
select is(public.user_balance('f1000000-0000-0000-0000-000000000001'), 30, 'the referrer is over the monthly cap');
select is((select status || '/' || referrer_rewarded::text from public.referrals where referee_id = 'f5000000-0000-0000-0000-000000000005'),
          'qualified/false', 'recorded as qualified, not rewarded');

-- A joined friend who never pays earns nothing, and users cannot read referrals.
select public.record_signup_source('f7000000-0000-0000-0000-000000000007',
       jsonb_build_object('ref', 'u_' || public.referral_code('f1000000-0000-0000-0000-000000000001')));
select is(public.user_balance('f7000000-0000-0000-0000-000000000007'), 30, 'no payment, no bonus');
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"f1000000-0000-0000-0000-000000000001","role":"authenticated"}', true);
select throws_ok($$ select * from public.referrals $$, '42501', null, 'users cannot read referrals directly');
select is((select count(*)::int from public.referral_codes), 1, 'a user sees only their own code');
reset role;

-- ---------------------------------------------------------------------------------------------
-- Plan-credit rollover
-- ---------------------------------------------------------------------------------------------
set local role service_role;
select is(public.billing_apply_event('evt_pl01', 'transaction.completed', now(),
  '{"kind":"grant_subscription","user_id":"f6000000-0000-0000-0000-000000000006","customer_id":"ctm_plan",
    "transaction_id":"txn_pl1","subscription_id":"sub_pl","plan":"creator","credits":400,
    "period_start":"2026-06-01T00:00:00Z","period_end":"2026-07-01T00:00:00Z","total_minor":1900,"currency_code":"USD"}') ->> 'outcome',
  'granted', 'a June plan period');
select is((select expires_at from public.credit_ledger where user_id = 'f6000000-0000-0000-0000-000000000006' and reason = 'plan_grant'),
          '2026-08-01T00:00:00Z'::timestamptz, 'June''s credits expire when July ends');
select public.billing_apply_event('evt_pl02', 'transaction.completed', now(),
  '{"kind":"grant_pack","user_id":"f6000000-0000-0000-0000-000000000006","customer_id":"ctm_plan",
    "transaction_id":"txn_pl2","credits":250,"total_minor":1200,"currency_code":"USD"}');
select is((select expires_at from public.credit_ledger where ref = 'paddle:txn:txn_pl2'), null, 'pack credits never expire');
insert into public.credit_ledger (user_id, amount, reason, ref)
values ('f6000000-0000-0000-0000-000000000006', -150, 'render_final', 'test:spend:pl');
select is(public.expire_plan_credits(), 250, 'the unused 250 of June''s 400 expire (spends use plan credits first)');
select is(public.user_balance('f6000000-0000-0000-0000-000000000006'), 280, '30 + 400 + 250 - 150 - 250 expired');
select is(public.expire_plan_credits(), 0, 'the sweep is idempotent');
reset role;

select * from finish();
rollback;
