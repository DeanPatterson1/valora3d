-- pgTAP: analytics, attribution, feature flags, client errors, owner alerts, growth (20260930110000_analytics.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(90);

-- A = admin, B = customer (confirmed), C = confirms later.
set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at) values
  ('a1000000-0000-0000-0000-00000000000a', 'owner@example.com', now()),
  ('b1000000-0000-0000-0000-00000000000b', 'buyer@example.com', now()),
  ('c1000000-0000-0000-0000-00000000000c', 'later@example.com', null);
reset role;
insert into public.admins (user_id, note) values ('a1000000-0000-0000-0000-00000000000a', 'owner');

-- ---------------------------------------------------------------- signup_complete
select is((select count(*)::integer from public.product_events where event = 'signup_complete'), 2,
  'a confirmed signup records signup_complete (admin + customer)');
select is((select count(*)::integer from public.product_events where user_id = 'c1000000-0000-0000-0000-00000000000c'), 0,
  'an unconfirmed signup records nothing yet');
set local role supabase_auth_admin;
update auth.users set email_confirmed_at = now() where id = 'c1000000-0000-0000-0000-00000000000c';
update auth.users set email_confirmed_at = now() where id = 'c1000000-0000-0000-0000-00000000000c';
reset role;
select is((select count(*)::integer from public.product_events
            where user_id = 'c1000000-0000-0000-0000-00000000000c' and event = 'signup_complete'), 1,
  'confirming records signup_complete once');

-- ---------------------------------------------------------------- first_project (inserted by the user under RLS)
set local role authenticated;
set local request.jwt.claims to '{"sub":"b1000000-0000-0000-0000-00000000000b","role":"authenticated"}';
insert into public.projects (id, user_id, name) values
  ('b2000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-00000000000b', 'One'),
  ('b2000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-00000000000b', 'Two');
select throws_ok($$ select count(*) from public.product_events $$, '42501', null, 'users cannot read product_events');
select throws_ok($$ insert into public.product_events (event, user_id, source)
  values ('checkout_complete', 'b1000000-0000-0000-0000-00000000000b', 'server') $$, '42501', null,
  'users cannot write any other event');
select throws_ok($$ insert into public.product_events (event, user_id, source)
  values ('first_project', 'c1000000-0000-0000-0000-00000000000c', 'server') $$, '42501', null,
  'users cannot write an event for someone else');
select throws_ok($$ select count(*) from public.feature_flags $$, '42501', null, 'users cannot read feature_flags');
select throws_ok($$ select count(*) from public.client_errors $$, '42501', null, 'users cannot read client_errors');
select throws_ok($$ select public.record_client_events('abcdefghijklmnop', null, '[]') $$, '42501', null,
  'users cannot call record_client_events');
select throws_ok($$ select public.admin_growth('{}', 30) $$, '42501', null, 'users cannot call admin_growth');
select throws_ok($$ update public.profiles set signup_source = '{"source":"x"}' where id = 'b1000000-0000-0000-0000-00000000000b' $$,
  '42501', null, 'users cannot write their own signup_source');
reset role;
select is((select count(*)::integer from public.product_events
            where user_id = 'b1000000-0000-0000-0000-00000000000b' and event = 'first_project'), 1,
  'two projects record first_project once');

-- ---------------------------------------------------------------- uploads
insert into public.uploads (id, user_id, project_id, source, file_name, r2_key, size_bytes) values
  ('b3000000-0000-4000-8000-000000000001', 'b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001',
   'upload', 'car.glb', 'u/b1000000-0000-0000-0000-00000000000b/b3000000-0000-4000-8000-000000000001.glb', 1000),
  ('b3000000-0000-4000-8000-000000000002', 'b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001',
   'upload', 'bad.glb', 'u/b1000000-0000-0000-0000-00000000000b/b3000000-0000-4000-8000-000000000002.glb', 1000),
  ('b3000000-0000-4000-8000-000000000003', 'b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001',
   'upload', 'old.glb', 'u/b1000000-0000-0000-0000-00000000000b/b3000000-0000-4000-8000-000000000003.glb', 1000);
update public.uploads set status = 'ready', completed_at = now() where id = 'b3000000-0000-4000-8000-000000000001';
update public.uploads set status = 'rejected', reject_reason = 'The uploaded file is empty.' where id = 'b3000000-0000-4000-8000-000000000002';
update public.uploads set status = 'rejected', reject_reason = 'expired' where id = 'b3000000-0000-4000-8000-000000000003';
select is((select count(*)::integer from public.product_events where event = 'upload_start'), 3, 'each upload records upload_start');
select is((select count(*)::integer from public.product_events where event = 'upload_ready'), 1, 'a verified upload records upload_ready');
select is((select props ->> 'reason' from public.product_events where event = 'upload_rejected'), 'empty',
  'a rejected upload records a coarse reason, never the text');
select is((select count(*)::integer from public.product_events where event = 'upload_rejected'), 1,
  'a retention expiry is not a rejection');

-- ---------------------------------------------------------------- scene versions + renders
insert into public.scene_versions (project_id, user_id, index, plan) values
  ('b2000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-00000000000b', 0, '{}'),
  ('b2000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-00000000000b', 1, '{}');
select is((select array_agg(event order by id) from public.product_events where event like 'scene_%'),
  array['scene_generated', 'scene_saved'], 'first version is scene_generated, then scene_saved');

-- The Free grant (10) covers two previews at 5 and nothing more; the last render below needs another 5.
insert into public.credit_ledger (user_id, amount, reason, ref)
values ('b1000000-0000-0000-0000-00000000000b', 10, 'admin_adjustment', 'test:analytics-topup');
select public.create_render_job('b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', null,
  'b3000000-0000-4000-8000-000000000001', 'preview', '{"prompt":"a","tier":"preview"}', 5, 'an-job-0001');
select is((select props ->> 'tier' from public.product_events where event = 'render_requested'), 'preview',
  'a created job records render_requested with its tier');
update public.render_jobs set status = 'succeeded', finished_at = now(), gpu_seconds = 40 where idempotency_key = 'an-job-0001';
select is((select count(*)::integer from public.product_events where event = 'render_succeeded'), 1, 'success records render_succeeded');
update public.render_jobs set stage = 'done' where idempotency_key = 'an-job-0001';
select is((select count(*)::integer from public.product_events where event = 'render_succeeded'), 1, 'other updates record nothing more');
select public.create_render_job('b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', null,
  'b3000000-0000-4000-8000-000000000001', 'preview', '{"prompt":"b","tier":"preview"}', 5, 'an-job-0002');
update public.render_jobs set status = 'failed', finished_at = now(), error_code = 'WORKER_MISCONFIGURED', execution_ms = 5000
 where idempotency_key = 'an-job-0002';
select is((select props from public.product_events where event = 'render_failed'),
  '{"tier": "preview", "code": "WORKER_MISCONFIGURED"}'::jsonb, 'a failure records render_failed with tier and code');

-- ---------------------------------------------------------------- per-job cost
select is(public.set_render_job_cost((select id from public.render_jobs where idempotency_key = 'an-job-0001'), 0.01224, 18000, 4000),
  true, 'the cost is written at finish');
select is(public.set_render_job_cost((select id from public.render_jobs where idempotency_key = 'an-job-0001'), 9, null, null),
  false, 'a second write changes nothing');
select is((select cost_usd_estimate from public.render_jobs where idempotency_key = 'an-job-0001'), 0.0122::numeric,
  'the cost is stored to 4 places');
select is((select director_input_tokens from public.render_jobs where idempotency_key = 'an-job-0001'), 18000, 'director tokens are stored');
select throws_ok($$ select public.set_render_job_cost((select id from public.render_jobs where idempotency_key = 'an-job-0002'), -1, null, null) $$,
  '22023', null, 'a negative cost is refused');

-- ---------------------------------------------------------------- kill switches + capacity guard
select is(public.flag_enabled('renders_enabled'), true, 'renders are on by default');
select is(public.flag_enabled('no_such_flag'), true, 'a missing flag reads as on');
update public.feature_flags set enabled = false where key = 'renders_enabled';
select throws_ok($$ select public.create_render_job('b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', null,
  'b3000000-0000-4000-8000-000000000001', 'preview', '{"prompt":"c","tier":"preview"}', 5, 'an-job-0003') $$,
  'P0001', 'renders_paused', 'renders_enabled off refuses create_render_job');
select is(public.user_balance('b1000000-0000-0000-0000-00000000000b'), 10, 'a refused render charges nothing');
update public.feature_flags set enabled = true where key = 'renders_enabled';
update public.feature_flags set enabled = false where key = 'finals_enabled';
select throws_ok($$ insert into public.render_jobs (user_id, project_id, kind, cost_credits)
  values ('b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', 'final', 0) $$,
  'P0001', 'finals_paused', 'finals_enabled off refuses a final');
select lives_ok($$ insert into public.render_jobs (user_id, project_id, kind, cost_credits, status)
  values ('b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', 'preview', 0, 'running') $$,
  'finals_enabled off still allows a preview');
update public.feature_flags set enabled = true where key = 'finals_enabled';

-- The one live render belongs to someone else (the admin), so only the global cap can refuse B.
update public.render_jobs set status = 'cancelled', finished_at = now() where status = 'running';
insert into public.projects (id, user_id, name) values ('a2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-00000000000a', 'Ops');
insert into public.render_jobs (user_id, project_id, kind, cost_credits, status)
values ('a1000000-0000-0000-0000-00000000000a', 'a2000000-0000-0000-0000-000000000001', 'preview', 0, 'running');
update public.feature_flags set value = 1 where key = 'global_max_active_renders';
select throws_ok($$ select public.create_render_job('b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', null,
  'b3000000-0000-4000-8000-000000000001', 'preview', '{"prompt":"d","tier":"preview"}', 5, 'an-job-0004') $$,
  'P0001', 'high_demand: capacity', 'the global concurrency cap refuses a new render');
update public.feature_flags set value = null where key = 'global_max_active_renders';
update public.render_jobs set status = 'cancelled', finished_at = now() where status = 'running';

select is(public.gpu_seconds_today(), 45.0::numeric, 'gpu seconds today: measured 40 + 5 s billed execution');
update public.feature_flags set value = 45 where key = 'daily_gpu_budget_seconds';
select throws_ok($$ select public.create_render_job('b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', null,
  'b3000000-0000-4000-8000-000000000001', 'preview', '{"prompt":"e","tier":"preview"}', 5, 'an-job-0005') $$,
  'P0001', 'high_demand: budget', 'the daily GPU budget refuses a new render');
update public.feature_flags set value = 10000 where key = 'daily_gpu_budget_seconds';
select lives_ok($$ select public.create_render_job('b1000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', null,
  'b3000000-0000-4000-8000-000000000001', 'preview', '{"prompt":"f","tier":"preview"}', 5, 'an-job-0006') $$,
  'under the budget a render starts');
select is(public.gpu_seconds_today(), 765.0::numeric, 'an in-flight preview counts its estimate (720 s)');
update public.feature_flags set value = null where key = 'daily_gpu_budget_seconds';

update public.feature_flags set enabled = false where key = 'signups_enabled';
set local role supabase_auth_admin;
select throws_ok($$ insert into auth.users (id, email) values ('d1000000-0000-0000-0000-00000000000d', 'new@example.com') $$,
  'P0001', 'signups_paused', 'signups_enabled off refuses a new account');
reset role;
update public.feature_flags set enabled = true where key = 'signups_enabled';

-- ---------------------------------------------------------------- admin_set_flag (audited)
select throws_ok($$ select public.admin_set_flag('b1000000-0000-0000-0000-00000000000b', 'renders_enabled', false, null, null, null,
  'turn it off', 'req-flag-evil') $$, '42501', null, 'a non-admin cannot change a flag');
select is((public.admin_set_flag('a1000000-0000-0000-0000-00000000000a', 'sharing_enabled', false, 50,
  array['b1000000-0000-0000-0000-00000000000b']::uuid[], null, 'abuse wave', 'req-flag-0001') -> 'flag' ->> 'enabled')::boolean,
  false, 'an admin turns a flag off');
select is((select rollout_percent from public.feature_flags where key = 'sharing_enabled'), 50::smallint, 'the rollout is stored');
select is((select updated_by from public.feature_flags where key = 'sharing_enabled'), 'a1000000-0000-0000-0000-00000000000a'::uuid,
  'updated_by names the admin');
select is((select detail -> 'before' ->> 'enabled' from public.admin_audit_log where request_id = 'req-flag-0001'), 'true',
  'the audit row keeps the value before');
select is((select detail -> 'after' ->> 'enabled' from public.admin_audit_log where request_id = 'req-flag-0001'), 'false',
  'and after');
select is((public.admin_set_flag('a1000000-0000-0000-0000-00000000000a', 'sharing_enabled', false, 50, null, null,
  'abuse wave', 'req-flag-0001') ->> 'replay')::boolean, true, 'the same request id is a replay');
select is((select count(*)::integer from public.admin_audit_log where action = 'flag_update'), 1, 'one audit row');
select throws_ok($$ select public.admin_set_flag('a1000000-0000-0000-0000-00000000000a', 'nope_flag', true, null, null, null,
  'typo', 'req-flag-0002') $$, 'P0002', null, 'an unknown flag is refused');
select throws_ok($$ select public.admin_set_flag('a1000000-0000-0000-0000-00000000000a', 'sharing_enabled', true, 150, null, null,
  'bad rollout', 'req-flag-0003') $$, '22023', null, 'a rollout over 100 is refused');
select is((public.admin_set_flag('a1000000-0000-0000-0000-00000000000a', 'global_max_active_renders', null, null, null, 12,
  'cap the fleet', 'req-flag-0004') -> 'flag' ->> 'value')::numeric, 12::numeric, 'a setting takes a value');
select is(public.setting_value('global_max_active_renders'), 12::numeric, 'setting_value reads it');
select is((public.admin_set_flag('a1000000-0000-0000-0000-00000000000a', 'renders_enabled', true, null, null, 5,
  'value on a flag', 'req-flag-0005') -> 'flag' ->> 'value'), null, 'a flag never keeps a value');

-- ---------------------------------------------------------------- browser events
select is(public.record_client_events('sess_abcdefghijklmnop', null,
  '[{"event":"landing_view","path":"/"},{"event":"cta_click","path":"/","props":{"cta":"hero_signup"}}]'), 2,
  'a browser batch is recorded');
select is((select count(*)::integer from public.product_events where session_id = 'sess_abcdefghijklmnop' and source = 'client'), 2,
  'with its session id, as client events');
select throws_ok($$ select public.record_client_events('sess_abcdefghijklmnop', null, '[{"event":"checkout_complete"}]') $$,
  '22023', null, 'a browser cannot send a server event');
select throws_ok($$ select public.record_client_events('bad id', null, '[{"event":"landing_view"}]') $$,
  '22023', null, 'a malformed session id is refused');
select throws_ok($$ select public.record_client_events('sess_abcdefghijklmnop', null, '[{"event":"landing_view","path":"/p?email=x"}]') $$,
  '23514', null, 'a path with a query is refused');
insert into public.product_events (event, session_id, source)
select 'pricing_view', 'sess_flooder_000000000', 'client' from generate_series(1, 300);
select is(public.record_client_events('sess_flooder_000000000', null, '[{"event":"landing_view","path":"/"}]'), 0,
  'past the hourly ceiling a batch is dropped');
select throws_ok($$ select public.record_product_event('landing_view', null, '{}', '/') $$, '22023', null,
  'record_product_event is for server events only');
select is(public.record_product_event('experiment_exposure', null, '{"key":"hero","variant":"control"}', null), true,
  'the experiment helper logs exposures server-side too');
select is(public.record_product_event('checkout_open', 'b1000000-0000-0000-0000-00000000000b', '{"item":"pack:100"}', '/pricing'), true,
  'a route records its own event');

-- ---------------------------------------------------------------- attribution
select is(public.record_signup_source('b1000000-0000-0000-0000-00000000000b',
  '{"source":"newsletter","medium":"email","ref":"share_AAAAAAAAAAAAAAAAAAAAAAAA","landing":"/"}'), true,
  'a new account gets its signup source');
select is(public.record_signup_source('b1000000-0000-0000-0000-00000000000b', '{"source":"other"}'), false, 'only once');
select is((select signup_source ->> 'source' from public.profiles where id = 'b1000000-0000-0000-0000-00000000000b'), 'newsletter',
  'the first source is kept');
select is((select count(*)::integer from public.product_events where event = 'share_signup'), 1, 'a share ref records share_signup');
select is(public.record_signup_source('c1000000-0000-0000-0000-00000000000c', '{"evil":"x"}'), false, 'unknown keys are refused');
update public.profiles set created_at = now() - interval '3 days' where id = 'c1000000-0000-0000-0000-00000000000c';
select is(public.record_signup_source('c1000000-0000-0000-0000-00000000000c', '{"source":"late"}'), false,
  'an account older than a day is not re-attributed');

-- ---------------------------------------------------------------- billing events + transaction source
insert into public.billing_transactions (id, user_id, kind, credits_granted, total_minor, currency_code)
values ('txn_pack1', 'b1000000-0000-0000-0000-00000000000b', 'pack', 100, 500, 'USD');
select is((select props ->> 'item' from public.product_events where event = 'checkout_complete'), 'pack:100',
  'a pack purchase records checkout_complete');
select is((select source ->> 'source' from public.billing_transactions where id = 'txn_pack1'), 'newsletter',
  'a transaction takes the buyer''s signup source');
select is(public.billing_set_transaction_source('txn_pack1', '{"source":"spring","medium":"cpc"}'), true,
  'checkout custom data overrides it');
select is((select source ->> 'source' from public.billing_transactions where id = 'txn_pack1'), 'spring', 'stored');
insert into public.billing_transactions (id, user_id, kind, subscription_id, plan, credits_granted, total_minor, created_at) values
  ('txn_sub1', 'b1000000-0000-0000-0000-00000000000b', 'subscription', 'sub_b1', 'creator', 500, 1900, now() - interval '31 days');
insert into public.billing_transactions (id, user_id, kind, subscription_id, plan, credits_granted, total_minor) values
  ('txn_sub2', 'b1000000-0000-0000-0000-00000000000b', 'subscription', 'sub_b1', 'creator', 500, 1900);
insert into public.billing_transactions (id, user_id, kind, subscription_id, plan, credits_granted, total_minor) values
  ('txn_sub3', 'b1000000-0000-0000-0000-00000000000b', 'subscription', 'sub_b1', 'pro', 1500, 3000);
select is((select array_agg(props ->> 'item' order by id) from public.product_events where event = 'checkout_complete'),
  array['pack:100', 'plan:creator', 'plan:pro'], 'first period and upgrade are checkouts, a renewal is not');

insert into public.billing_subscriptions (id, user_id, plan, status, paid_through)
values ('sub_b1', 'b1000000-0000-0000-0000-00000000000b', 'pro', 'active', now() + interval '20 days');
update public.billing_subscriptions set status = 'canceled' where id = 'sub_b1';
update public.billing_subscriptions set status = 'canceled' where id = 'sub_b1';
select is((select count(*)::integer from public.product_events where event = 'plan_canceled'), 1, 'a cancel records plan_canceled once');

-- ---------------------------------------------------------------- shares
insert into public.render_shares (slug, job_id, user_id)
values ('SSSSSSSSSSSSSSSSSSSSSSSS', (select id from public.render_jobs where idempotency_key = 'an-job-0001'),
        'b1000000-0000-0000-0000-00000000000b');
select public.bump_render_share_view('SSSSSSSSSSSSSSSSSSSSSSSS');
select public.bump_render_share_view('SSSSSSSSSSSSSSSSSSSSSSSS');
select is((select count(*)::integer from public.product_events where event = 'share_created'), 1, 'a share records share_created');
select is((select count(*)::integer from public.product_events where event = 'share_view' and user_id is null), 2,
  'each counted view records an anonymous share_view');

-- ---------------------------------------------------------------- client errors
select is(public.record_client_error('abc1234', '/projects/[id]', 'TypeError', '1234567890', 'segment', 'chrome'), true,
  'a client error is recorded');
select public.record_client_error('abc1234', '/projects/[id]', 'TypeError', null, 'segment', 'firefox');
select throws_ok($$ select public.record_client_error('abc1234', '/projects/12?token=x', 'TypeError', null, 'segment', 'chrome') $$,
  '23514', null, 'a path with a query is refused');
select throws_ok($$ select public.record_client_error('abc1234', '/', 'Cannot read x of undefined', null, 'global', 'chrome') $$,
  '23514', null, 'a message in place of the name is refused');
select is((public.admin_client_errors(now() - interval '1 day') -> 0 ->> 'count')::integer, 2,
  'errors are grouped by release, path and name');
insert into public.client_errors (release, path, name, kind, ua_family, created_at)
values ('old1', '/', 'Error', 'global', 'chrome', now() - interval '31 days');
select is((public.prune_ops_data() ->> 'client_errors')::integer, 1, 'the sweep prunes errors older than 30 days');

-- ---------------------------------------------------------------- owner alerts + ops reads
select is(public.claim_owner_alert('failure_rate', 3600), true, 'the first alert of a kind is claimed');
select is(public.claim_owner_alert('failure_rate', 3600), false, 'the next one inside the hour is not');
select is((public.ops_alert_signals() ->> 'worker_misconfigured')::integer, 1, 'the WORKER_MISCONFIGURED failure is counted');
select is((public.ops_daily_digest(now() - interval '1 day') -> 'failures_by_code' ->> 'WORKER_MISCONFIGURED')::integer, 1,
  'the digest groups failures by code');

-- ---------------------------------------------------------------- growth
select is(jsonb_array_length(public.admin_growth('{"creator":1900,"pro":4900}', 30) -> 'north_star' -> 'weeks'), 12,
  'the north star has 12 weeks');
select is((public.admin_growth('{"creator":1900,"pro":4900}', 30) -> 'north_star' -> 'weeks' -> 11 ->> 'renders')::integer, 1,
  'this week''s delivered renders');
select is((public.admin_growth('{}', 30) -> 'signups' ->> 'today')::integer, 1, 'signups exclude admins (and backdated accounts)');
select is(jsonb_array_length(public.admin_growth('{}', 30) -> 'funnel' -> 'steps'), 7, 'the funnel has seven steps');
select is((select count(*)::integer from jsonb_array_elements(public.admin_growth('{}', 30) -> 'sources') e
            where e ->> 'source' = 'newsletter' and (e ->> 'paid')::integer = 1), 1, 'sources come from signup_source, with paid counts');

-- ---------------------------------------------------------------- append-only, account deletion
select throws_ok($$ update public.product_events set event = 'landing_view' where event = 'share_view' $$, '42501', null,
  'product_events cannot be edited');
delete from auth.users where id = 'c1000000-0000-0000-0000-00000000000c';
select is((select count(*)::integer from public.product_events where event = 'signup_complete' and user_id is null), 1,
  'a deleted account keeps its events, without the user id');

select * from finish();
rollback;
