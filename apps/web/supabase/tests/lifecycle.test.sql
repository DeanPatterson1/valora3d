-- pgTAP: lifecycle email, suppressions, feedback, cancellation feedback, data export (20260930130000_lifecycle.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(55);

-- N = new (confirmed today), D = day 3 without a render, T = day 8 with a render, W = inactive 40 days,
-- S = suppressed address, O = opted out of tips.
set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at) values
  ('10000000-0000-0000-0000-00000000000a', 'new@example.com', now()),
  ('20000000-0000-0000-0000-00000000000b', 'day3@example.com', now()),
  ('30000000-0000-0000-0000-00000000000c', 'day8@example.com', now()),
  ('40000000-0000-0000-0000-00000000000d', 'gone@example.com', now()),
  ('50000000-0000-0000-0000-00000000000e', 'Bounced@Example.com', now()),
  ('60000000-0000-0000-0000-00000000000f', 'quiet@example.com', now());
reset role;

-- Move the confirmations back in time (product_events is append-only; the service role may delete and re-insert).
delete from public.product_events where event = 'signup_complete'
   and user_id in ('20000000-0000-0000-0000-00000000000b', '30000000-0000-0000-0000-00000000000c', '40000000-0000-0000-0000-00000000000d');
insert into public.product_events (event, user_id, source, created_at) values
  ('signup_complete', '20000000-0000-0000-0000-00000000000b', 'server', now() - interval '3 days'),
  ('signup_complete', '30000000-0000-0000-0000-00000000000c', 'server', now() - interval '8 days'),
  ('signup_complete', '40000000-0000-0000-0000-00000000000d', 'server', now() - interval '40 days');
update public.profiles set created_at = now() - interval '40 days' where id = '40000000-0000-0000-0000-00000000000d';
update public.profiles set email_product_tips = false where id = '60000000-0000-0000-0000-00000000000f';

-- T has a delivered render.
insert into public.projects (id, user_id, name, updated_at) values
  ('30000000-0000-0000-0000-0000000000a1', '30000000-0000-0000-0000-00000000000c', 'Watch', now() - interval '8 days');
insert into public.render_jobs (id, user_id, project_id, kind, status, cost_credits, retention_days, finished_at, created_at)
values ('30000000-0000-0000-0000-0000000000b1', '30000000-0000-0000-0000-00000000000c', '30000000-0000-0000-0000-0000000000a1',
        'preview', 'succeeded', 5, 7, now() - interval '5 days', now() - interval '8 days');

-- ---------------------------------------------------------------- suppression list
select ok(public.record_email_suppression(' BOUNCED@example.com ', 'bounce', 'msg_1'), 'a bounce is recorded');
select is((select email from public.email_suppressions), 'bounced@example.com', 'addresses are stored lower-cased and trimmed');
select ok(public.record_email_suppression('bounced@example.com', 'complaint', 'msg_2'), 'a complaint on the same address');
select is((select reason from public.email_suppressions), 'complaint', 'a complaint outranks a bounce');
select ok(public.record_email_suppression('bounced@example.com', 'bounce', 'msg_3'), 'a later bounce');
select is((select reason from public.email_suppressions), 'complaint', 'a later bounce does not downgrade a complaint');
select throws_ok($$ select public.record_email_suppression('not-an-email', 'bounce', null) $$, '22023', null, 'garbage is refused');
select ok(public.email_suppressed('Bounced@Example.com'), 'lookups ignore case');

-- ---------------------------------------------------------------- who is due what
select is((select array_agg(user_id::text order by user_id) from public.due_lifecycle_emails('welcome', 50)),
  array['10000000-0000-0000-0000-00000000000a'],
  'welcome: only accounts confirmed in the last 3 days, minus suppressed and opted-out addresses');
select is((select array_agg(user_id::text) from public.due_lifecycle_emails('activation_nudge', 50)),
  array['20000000-0000-0000-0000-00000000000b'], 'nudge: 2-5 days in with no delivered render');
select is((select array_agg(user_id::text) from public.due_lifecycle_emails('tips', 50)),
  array['30000000-0000-0000-0000-00000000000c'], 'tips: 7-10 days in and activated');
select is((select array_agg(user_id::text) from public.due_lifecycle_emails('winback', 50)),
  array['40000000-0000-0000-0000-00000000000d'], 'win-back: 30+ days without activity');
select throws_ok($$ select * from public.due_lifecycle_emails('past_due', 5) $$, '22023', null,
  'billing kinds are not lifecycle kinds');

-- ---------------------------------------------------------------- claim_email
select is(public.claim_email('10000000-0000-0000-0000-00000000000a', 'welcome', 'once'), 'claimed', 'first claim wins');
select is(public.claim_email('10000000-0000-0000-0000-00000000000a', 'welcome', 'once'), 'duplicate', 'a second claim is a duplicate');
select is((select count(*)::integer from public.due_lifecycle_emails('welcome', 50)), 0, 'a sent welcome is no longer due');
select is(public.claim_email('50000000-0000-0000-0000-00000000000e', 'welcome', 'once'), 'suppressed',
  'no product mail to a suppressed address');
select is(public.claim_email('50000000-0000-0000-0000-00000000000e', 'past_due', 'sub_x:20261001'), 'claimed',
  'transactional mail ignores the suppression list');
select is(public.claim_email('60000000-0000-0000-0000-00000000000f', 'tips', 'once'), 'opted_out', 'tips respect the preference');
update public.profiles set email_render_ready = false where id = '60000000-0000-0000-0000-00000000000f';
select is(public.claim_email('60000000-0000-0000-0000-00000000000f', 'expiry_warning', '2026-10-01'), 'opted_out',
  'expiry warnings follow the render notifications preference');
select is(public.claim_email('60000000-0000-0000-0000-00000000000f', 'plan_canceled', 'sub_q'), 'claimed',
  'account mail is sent even when every opt-out is off');
select is(public.claim_email('10000000-0000-0000-0000-00000000000a', 'expiry_warning', 'd1'), 'claimed', 'second product mail today');
select is(public.claim_email('10000000-0000-0000-0000-00000000000a', 'tips', 'once'), 'rate_limited',
  'a third product mail in 24 hours is held back');
select is(public.claim_email('10000000-0000-0000-0000-00000000000a', 'cancel_scheduled', 'sub_n'), 'claimed',
  'the product-mail cap does not block account mail');
select is(public.claim_email('99999999-0000-0000-0000-000000000000', 'welcome', 'once'), 'no_profile', 'unknown account');
select throws_ok($$ select public.claim_email('10000000-0000-0000-0000-00000000000a', 'spam', 'once') $$, '22023', null,
  'unknown kinds are refused');
select lives_ok($$ select public.release_email('10000000-0000-0000-0000-00000000000a', 'expiry_warning', 'd1') $$, 'release');
select is((select count(*)::integer from public.email_log where kind = 'expiry_warning' and user_id = '10000000-0000-0000-0000-00000000000a'),
  0, 'a released claim is gone, so the next sweep retries');

-- ---------------------------------------------------------------- expiry warnings
-- T's render finished 5 days ago with 7-day retention: expires in 2 days, inside Free's 3-day lead.
insert into public.projects (id, user_id, name) values
  ('20000000-0000-0000-0000-0000000000a1', '20000000-0000-0000-0000-00000000000b', 'Car');
insert into public.render_jobs (id, user_id, project_id, kind, status, cost_credits, retention_days, finished_at) values
  -- paid, 30-day retention, expires in 5 days: inside the 7-day lead
  ('20000000-0000-0000-0000-0000000000b1', '20000000-0000-0000-0000-00000000000b', '20000000-0000-0000-0000-0000000000a1',
   'final', 'succeeded', 100, 30, now() - interval '25 days'),
  -- paid, expires in 20 days: not yet
  ('20000000-0000-0000-0000-0000000000b2', '20000000-0000-0000-0000-00000000000b', '20000000-0000-0000-0000-0000000000a1',
   'final', 'succeeded', 100, 30, now() - interval '10 days'),
  -- failed renders are never warned about
  ('20000000-0000-0000-0000-0000000000b3', '20000000-0000-0000-0000-00000000000b', '20000000-0000-0000-0000-0000000000a1',
   'final', 'failed', 100, 30, now() - interval '25 days');
select is((select count(*)::integer from public.due_expiry_warnings(50)), 2, 'one row per user with renders expiring soon');
select is((select render_count from public.due_expiry_warnings(50) where user_id = '20000000-0000-0000-0000-00000000000b'), 1,
  'only succeeded renders inside the lead window');
select is(public.expiry_warning_lead_days(7), 3, 'Free: 3 days ahead');
select is(public.expiry_warning_lead_days(30), 7, 'paid: 7 days ahead');
select is(public.mark_expiry_warned(array['20000000-0000-0000-0000-0000000000b1', '30000000-0000-0000-0000-0000000000b1']::uuid[]), 2,
  'marked');
select is((select count(*)::integer from public.due_expiry_warnings(50)), 0, 'a warned render is not warned again');

-- ---------------------------------------------------------------- billing notices
insert into public.billing_subscriptions (id, user_id, plan, status, current_period_end, updated_at) values
  ('sub_due1', '30000000-0000-0000-0000-00000000000c', 'creator', 'past_due', '2026-10-15T00:00:00Z', now()),
  ('sub_old1', '20000000-0000-0000-0000-00000000000b', 'pro', 'past_due', '2026-01-15T00:00:00Z', now() - interval '30 days');
select is((select array_agg(kind || ' ' || ref) from public.due_billing_emails(null, 50)),
  array['past_due sub_due1:20261015'], 'past_due is due once per period; old history is not mailed');
select is(public.claim_email('30000000-0000-0000-0000-00000000000c', 'past_due', 'sub_due1:20261015'), 'claimed', 'claimed');
select is((select count(*)::integer from public.due_billing_emails(null, 50)), 0, 'and then not due again');
update public.billing_subscriptions set status = 'canceled', canceled_at = now() where id = 'sub_due1';
select is((select kind from public.due_billing_emails('30000000-0000-0000-0000-00000000000c', 50)), 'plan_canceled',
  'the final cancellation is due, narrowed to one account');
select is((select count(*)::integer from public.due_billing_emails('20000000-0000-0000-0000-00000000000b', 50)), 0,
  'narrowing excludes everyone else');

-- ---------------------------------------------------------------- feedback (RLS: insert own, no read)
set local role authenticated;
set local request.jwt.claims to '{"sub":"20000000-0000-0000-0000-00000000000b","role":"authenticated"}';
select lives_ok($$ insert into public.feedback (kind, message, page, release, ua_family)
  values ('bug', 'The render button did nothing.', '/projects/[id]', 'abc123', 'chrome') $$, 'a user files feedback');
select throws_ok($$ select message from public.feedback $$, '42501', null, 'users cannot read any feedback text');
select is((select count(*)::integer from public.feedback), 1, 'users see only the existence of their own rows');
select throws_ok($$ insert into public.feedback (user_id, kind, message) values ('30000000-0000-0000-0000-00000000000c', 'idea', 'Someone else') $$,
  '42501', null, 'users cannot file feedback as someone else');
select throws_ok($$ insert into public.feedback (kind, message, status) values ('idea', 'Pre-triaged', 'done') $$,
  '42501', null, 'users cannot set the status');
select throws_ok($$ update public.feedback set kind = 'idea' $$, '42501', null, 'users cannot edit feedback');
select throws_ok($$ insert into public.feedback (kind, message) values ('rant', 'Nope') $$, '23514', null, 'kinds are checked');
insert into public.feedback (kind, message) values ('idea', 'Two'), ('idea', 'Three'), ('idea', 'Four'), ('idea', 'Five');
select throws_ok($$ insert into public.feedback (kind, message) values ('idea', 'Six') $$, 'P0001', 'rate_limited',
  'five an hour per account');
select throws_ok($$ select * from public.email_log $$, '42501', null, 'users cannot read email_log');
select throws_ok($$ select * from public.email_suppressions $$, '42501', null, 'users cannot read suppressions');
select throws_ok($$ select * from public.cancellation_feedback $$, '42501', null, 'users cannot read cancellation reasons');
select throws_ok($$ select public.claim_email('20000000-0000-0000-0000-00000000000b', 'welcome', 'once') $$, '42501', null,
  'users cannot claim mail');
update public.profiles set email_product_tips = false where id = '20000000-0000-0000-0000-00000000000b';
reset role;
select is((select email_product_tips from public.profiles where id = '20000000-0000-0000-0000-00000000000b'), false,
  'a user can turn product tips off');
select is((select user_id::text from public.feedback where message like 'The render%'), '20000000-0000-0000-0000-00000000000b',
  'the row carries the filer''s id');

-- ---------------------------------------------------------------- data export limit
select ok(public.claim_data_export('20000000-0000-0000-0000-00000000000b'), 'first export today');
select ok(not public.claim_data_export('20000000-0000-0000-0000-00000000000b'), 'one export per 24 hours');

select * from finish();
rollback;
