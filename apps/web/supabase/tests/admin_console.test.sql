-- pgTAP: the admin console migration (admins, admin_audit_log, admin_* actions, billing_webhook_errors).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(43);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at) values
  ('a0000000-0000-0000-0000-00000000000a', 'owner@example.com', now()),
  ('b0000000-0000-0000-0000-00000000000b', 'customer@example.com', now());
reset role;

insert into public.admins (user_id, note) values ('a0000000-0000-0000-0000-00000000000a', 'owner');

select ok(public.is_admin('a0000000-0000-0000-0000-00000000000a'), 'the seeded owner is an admin');
select ok(not public.is_admin('b0000000-0000-0000-0000-00000000000b'), 'a customer is not');
select is(public.user_balance('b0000000-0000-0000-0000-00000000000b'), 50, 'customer starts with the free grant');

-- ---------------------------------------------------------------- credits
select is((public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a', 'b0000000-0000-0000-0000-00000000000b',
  25, 'Goodwill for a failed launch render', 'req-grant-0001') ->> 'balance')::integer, 75, 'a grant adds credits');
select is((public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a', 'b0000000-0000-0000-0000-00000000000b',
  25, 'Goodwill for a failed launch render', 'req-grant-0001') ->> 'replay')::boolean, true, 'the same request id is a replay');
select is(public.user_balance('b0000000-0000-0000-0000-00000000000b'), 75, 'a replay grants nothing more');
select is((select count(*)::integer from public.credit_ledger where reason = 'admin_adjustment'), 1, 'one ledger row for the grant');
select is((select ref from public.credit_ledger where reason = 'admin_adjustment'), 'admin:req-grant-0001', 'ledger ref names the request');
select is((select count(*)::integer from public.admin_audit_log where request_id = 'req-grant-0001'), 1, 'one audit row for the grant');
select is((select admin_id from public.admin_audit_log where request_id = 'req-grant-0001'),
  'a0000000-0000-0000-0000-00000000000a'::uuid, 'the audit row names the admin');
select is((select (detail ->> 'ledger_id')::bigint from public.admin_audit_log where request_id = 'req-grant-0001'),
  (select id from public.credit_ledger where ref = 'admin:req-grant-0001'), 'the audit row links the ledger row');
select throws_ok($$ select public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a',
  'b0000000-0000-0000-0000-00000000000b', 30, 'Goodwill for a failed launch render', 'req-grant-0001') $$,
  '23505', null, 'the same request id with another amount is refused');
select is((public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a', 'b0000000-0000-0000-0000-00000000000b',
  -100, 'Chargeback clawback', 'req-deduct-0002') ->> 'balance')::integer, -25, 'a deduction may go below zero');
select throws_ok($$ select public.admin_adjust_credits('b0000000-0000-0000-0000-00000000000b',
  'b0000000-0000-0000-0000-00000000000b', 1000, 'self service', 'req-evil-0003') $$,
  '42501', null, 'a non-admin cannot adjust credits');
select throws_ok($$ select public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a',
  'b0000000-0000-0000-0000-00000000000b', 10, '  ', 'req-noreason-04') $$,
  '22023', null, 'a reason is required');
select throws_ok($$ select public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a',
  'b0000000-0000-0000-0000-00000000000b', 0, 'nothing at all', 'req-zero-00005') $$,
  '22023', null, 'a zero amount is refused');
select throws_ok($$ select public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a',
  'b0000000-0000-0000-0000-00000000000b', 10, 'short id', 'x') $$,
  '22023', null, 'a request id is required');
select throws_ok($$ select public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a',
  gen_random_uuid(), 10, 'nobody home', 'req-nouser-006') $$,
  'P0002', null, 'an unknown user is refused');
select is((select count(*)::integer from public.admin_audit_log), 2, 'refused actions write no audit rows');

-- Back above zero for the render below.
select public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a', 'b0000000-0000-0000-0000-00000000000b',
  100, 'Top up for the test render', 'req-topup-0007');

-- ---------------------------------------------------------------- refunds
insert into public.projects (id, user_id, name)
values ('dddddddd-0000-0000-0000-0000000000a1', 'b0000000-0000-0000-0000-00000000000b', 'Admin test');
select public.create_render_job('b0000000-0000-0000-0000-00000000000b', 'dddddddd-0000-0000-0000-0000000000a1',
  null, null, 'preview', '{"prompt":"a","tier":"preview"}', 3, 'admin-job-key-1');
update public.render_jobs set runpod_id = 'rp-admin-1', status = 'running' where idempotency_key = 'admin-job-key-1';

select throws_ok($$ select public.admin_refund_render_job('a0000000-0000-0000-0000-00000000000a',
  (select id from public.render_jobs where runpod_id = 'rp-admin-1'), 'still running', 'req-refund-run1') $$,
  '22023', null, 'a live job cannot be refunded');

-- Cancelled after the GPU started: finished without a refund, then the operator refunds it.
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-admin-1'), 'rp-admin-1',
  'cancelled', 'Cancelled while rendering.', 'CANCELLED_BY_USER', false, '{}', false), 0, 'cancelled without a refund');
select is(public.user_balance('b0000000-0000-0000-0000-00000000000b'), 72, 'the debit stands');
select is((public.admin_refund_render_job('a0000000-0000-0000-0000-00000000000a',
  (select id from public.render_jobs where runpod_id = 'rp-admin-1'), 'GPU crash on our side', 'req-refund-0008') ->> 'refunded')::integer,
  3, 'the operator refund returns the debit');
select is(public.user_balance('b0000000-0000-0000-0000-00000000000b'), 75, 'balance restored');
select is((select refunded_credits from public.render_jobs where runpod_id = 'rp-admin-1'), 3, 'refunded_credits recorded');
select is((public.admin_refund_render_job('a0000000-0000-0000-0000-00000000000a',
  (select id from public.render_jobs where runpod_id = 'rp-admin-1'), 'GPU crash on our side', 'req-refund-0008') ->> 'replay')::boolean,
  true, 'the same refund request is a replay');
select is((public.admin_refund_render_job('a0000000-0000-0000-0000-00000000000a',
  (select id from public.render_jobs where runpod_id = 'rp-admin-1'), 'second try, new id', 'req-refund-0009') ->> 'refunded')::integer,
  0, 'a second refund request refunds nothing');
select is(public.user_balance('b0000000-0000-0000-0000-00000000000b'), 75, 'still refunded once');
select is((select count(*)::integer from public.admin_audit_log where action = 'render_refund'), 2, 'each refund request is audited once');

-- ---------------------------------------------------------------- record + append-only
select is(public.admin_record_action('a0000000-0000-0000-0000-00000000000a', 'render_retry', 'render_job',
  'dddddddd-0000-0000-0000-0000000000a1', 'retry', '{"new_job_id":"x"}', 'retry:job-0001'), true, 'a retry is recorded');
select is(public.admin_record_action('a0000000-0000-0000-0000-00000000000a', 'render_retry', 'render_job',
  'dddddddd-0000-0000-0000-0000000000a1', 'retry', '{"new_job_id":"x"}', 'retry:job-0001'), false, 'recorded once');
select throws_ok($$ update public.admin_audit_log set reason = 'rewritten' $$, '42501', null, 'the audit log cannot be edited');
select throws_ok($$ delete from public.admin_audit_log $$, '42501', null, 'the audit log cannot be deleted');

-- ---------------------------------------------------------------- overview + search + webhook errors
select public.log_billing_webhook_error('apply', 'evt_abc123', 'transaction.completed', 'P0001', 'no owner');
select is((select count(*)::integer from public.billing_webhook_errors), 1, 'webhook errors are logged');
select ok(public.admin_overview() ? 'windows' and (public.admin_overview() -> 'windows' -> 'd30' -> 'renders' ->> 'total')::integer = 1,
  'the overview counts renders');
select is((select count(*)::integer from public.admin_find_users('CUSTOMER@', 10)), 1, 'search by email fragment');
select is((select count(*)::integer from public.admin_find_users('%', 10)), 0, 'LIKE wildcards are matched literally');

-- ---------------------------------------------------------------- users
set local role authenticated;
set local request.jwt.claims to '{"sub":"b0000000-0000-0000-0000-00000000000b","role":"authenticated"}';
select is((select count(*)::integer from public.admins), 0, 'a customer sees no admin rows');
select throws_ok($$ select public.admin_adjust_credits('a0000000-0000-0000-0000-00000000000a',
  'b0000000-0000-0000-0000-00000000000b', 1000, 'impersonating', 'req-imper-0010') $$,
  '42501', null, 'users cannot call admin functions');
select throws_ok($$ select count(*) from public.admin_audit_log $$, '42501', null, 'users cannot read the audit log');
select throws_ok($$ select count(*) from public.billing_webhook_errors $$, '42501', null, 'users cannot read webhook errors');
select throws_ok($$ insert into public.admins (user_id) values ('b0000000-0000-0000-0000-00000000000b') $$,
  '42501', null, 'users cannot make themselves admins');
reset role;
set local role authenticated;
set local request.jwt.claims to '{"sub":"a0000000-0000-0000-0000-00000000000a","role":"authenticated"}';
select is((select count(*)::integer from public.admins), 1, 'an admin sees exactly their own row');
reset role;

select * from finish();
rollback;
