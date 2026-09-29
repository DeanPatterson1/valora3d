-- pgTAP: storage + render hardening (20260929200000_storage_security.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(52);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at) values
  ('55555555-5555-5555-5555-555555555555', 'store@example.com', now()),
  ('66666666-6666-6666-6666-666666666666', 'other@example.com', now());
reset role;

insert into public.projects (id, user_id, name) values
  ('eeeeeeee-0000-0000-0000-000000000001', '55555555-5555-5555-5555-555555555555', 'Keep'),
  ('eeeeeeee-0000-0000-0000-000000000002', '55555555-5555-5555-5555-555555555555', 'Delete me');
insert into public.credit_ledger (user_id, amount, reason, ref)
values ('55555555-5555-5555-5555-555555555555', 500, 'admin_adjustment', 'adj:storage-test');

-- ---------------------------------------------------------------- H2: no user DELETE on projects
set local role authenticated;
set local request.jwt.claims to '{"sub":"55555555-5555-5555-5555-555555555555","role":"authenticated"}';
select throws_ok($$ delete from public.projects where id = 'eeeeeeee-0000-0000-0000-000000000002' $$,
  '42501', null, 'users cannot delete a project through PostgREST');
select throws_ok($$ select count(*) from public.usage_events $$, '42501', null, 'users cannot read usage_events');
select throws_ok($$ select count(*) from public.storage_purge_queue $$, '42501', null, 'users cannot read the purge queue');
select throws_ok($$ select public.create_upload('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000002',
  gen_random_uuid(), 'u/55555555-5555-5555-5555-555555555555/x.glb', 'x.glb', 10, null) $$,
  '42501', null, 'users cannot call create_upload');
select throws_ok($$ select * from public.claim_storage_purges(10, null) $$, '42501', null, 'users cannot claim purges');
select throws_ok($$ select public.request_render_cancel(gen_random_uuid(), false) $$, '42501', null,
  'users cannot call request_render_cancel');
reset role;

-- ---------------------------------------------------------------- L8/H2: the upload cap, under the lock
select is(public.upload_daily_cap(), 30, 'upload cap is 30 a day (lib/usageLimits.ts)');
select public.create_upload('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000002',
  ('aaaaaaaa-0000-4000-8000-' || lpad(i::text, 12, '0'))::uuid,
  'u/55555555-5555-5555-5555-555555555555/aaaaaaaa-0000-4000-8000-' || lpad(i::text, 12, '0') || '.glb',
  'm.glb', 1000, null)
  from generate_series(1, 29) i;
select is(public.usage_count('55555555-5555-5555-5555-555555555555', 'upload'), 29, '29 uploads counted');
select throws_ok($$ select public.create_upload('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000009',
  gen_random_uuid(), 'u/55555555-5555-5555-5555-555555555555/x.glb', 'x.glb', 10, null) $$,
  'P0002', null, 'create_upload checks project ownership');
select throws_ok($$ select public.create_upload('66666666-6666-6666-6666-666666666666', 'eeeeeeee-0000-0000-0000-000000000002',
  gen_random_uuid(), 'u/66666666-6666-6666-6666-666666666666/x.glb', 'x.glb', 10, null) $$,
  'P0002', null, 'another user cannot upload into the project');

-- A ready upload and two jobs (one finished, one still running) in the project to delete.
update public.uploads set status = 'ready', completed_at = now() where id = 'aaaaaaaa-0000-4000-8000-000000000001';
select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000002',
  null, 'aaaaaaaa-0000-4000-8000-000000000001', 'preview', '{"prompt":"a","tier":"preview"}', 5, 'store-job-1');
update public.render_jobs set runpod_id = 'rp-s1' where idempotency_key = 'store-job-1';
select public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-s1'), 'rp-s1', 'succeeded',
  null, null, null, '{}', false);
select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000002',
  null, 'aaaaaaaa-0000-4000-8000-000000000001', 'preview', '{"prompt":"b","tier":"preview"}', 5, 'store-job-2');
update public.render_jobs set runpod_id = 'rp-s2', status = 'running', submitted_at = now() where idempotency_key = 'store-job-2';

-- The service role deletes the project (the API route): rows cascade, their R2 objects are queued.
set local role service_role;
delete from public.projects where id = 'eeeeeeee-0000-0000-0000-000000000002';
reset role;
select is((select count(*)::integer from public.uploads where project_id = 'eeeeeeee-0000-0000-0000-000000000002'), 0,
  'uploads cascaded');
select is(public.usage_count('55555555-5555-5555-5555-555555555555', 'upload'), 29,
  'deleting the project does not reset the upload count');
select is(public.usage_count('55555555-5555-5555-5555-555555555555', 'render'), 2,
  'deleting the project does not reset the render count');
select is((select count(*)::integer from public.storage_purge_queue
            where target like 'u/55555555-5555-5555-5555-555555555555/%.glb' and not_before <= now()), 29,
  'every deleted upload''s object is queued now');
select is((select count(*)::integer from public.storage_purge_queue
            where target like 'u/%.glb' and not_before > now()), 28,
  'pending uploads get a late sweep after their presigned PUT expires');
select is((select count(*)::integer from public.storage_purge_queue
            where target ~ '^r/55555555-5555-5555-5555-555555555555/[0-9a-f-]{36}/$' and not_before <= now()), 2,
  'both deleted jobs'' output prefixes are queued');
select is((select count(*)::integer from public.storage_purge_queue
            where target ~ '^r/55555555-5555-5555-5555-555555555555/[0-9a-f-]{36}/$' and not_before > now() + interval '24 hours'), 1,
  'the running job gets a late sweep after its output PUT URLs expire');
select is(public.render_put_window('preview'), interval '24 hours 50 minutes', 'preview PUT window (contract.ts)');
select is(public.render_put_window('final'), interval '26 hours 30 minutes', 'final PUT window (contract.ts)');

-- The cap still counts the deleted uploads: one more is allowed, the 31st is not.
select ok((select public.create_upload('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  gen_random_uuid(), 'u/55555555-5555-5555-5555-555555555555/bbbbbbbb-0000-4000-8000-000000000001.glb', 'm.glb', 10, null)).id is not null,
  'the 30th upload of the day is allowed');
select throws_ok($$ select public.create_upload('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  gen_random_uuid(), 'u/55555555-5555-5555-5555-555555555555/bbbbbbbb-0000-4000-8000-000000000002.glb', 'm.glb', 10, null) $$,
  'P0001', 'rate_limited: uploads', 'the 31st upload of the day is refused, even after deleting a project');

-- ---------------------------------------------------------------- the queue only takes the site's own shapes
select throws_ok($$ select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555', '', 'account_deleted') $$,
  '23514', null, 'an empty prefix (the whole bucket) is refused');
select throws_ok($$ select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555', 'u/66666666-6666-6666-6666-666666666666/', 'account_deleted') $$,
  '23514', null, 'another user''s prefix is refused');
select throws_ok($$ select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555', 'samples/', 'account_deleted') $$,
  '23514', null, 'shared prefixes are refused');

-- Claim, release (back off), complete (a prefix also clears the entries it covered).
delete from public.storage_purge_queue;
select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555', 'r/55555555-5555-5555-5555-555555555555/', 'account_deleted');
select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555',
  'r/55555555-5555-5555-5555-555555555555/bbbbbbbb-0000-4000-8000-000000000009/', 'render_deleted');
select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555',
  'r/55555555-5555-5555-5555-555555555555/bbbbbbbb-0000-4000-8000-000000000008/', 'render_deleted', now() + interval '1 day');
select public.enqueue_storage_purge('66666666-6666-6666-6666-666666666666', 'u/66666666-6666-6666-6666-666666666666/', 'account_deleted');
select is((select count(*)::integer from public.claim_storage_purges(10, '55555555-5555-5555-5555-555555555555')), 2,
  'claims only the owner''s due entries');
select is((select count(*)::integer from public.claim_storage_purges(10, '55555555-5555-5555-5555-555555555555')), 0,
  'a claimed entry is not claimed twice');
select is(public.release_storage_purges(array(select id from public.storage_purge_queue
  where target like 'r/55555555-5555-5555-5555-555555555555/bbbbbbbb-0000-4000-8000-000000000009/'), 'R2 503'), 1, 'release');
select ok((select not_before > now() and last_error = 'R2 503' from public.storage_purge_queue
            where target like '%bbbbbbbb-0000-4000-8000-000000000009/'), 'a released entry backs off');
select is(public.complete_storage_purges(array(select id from public.storage_purge_queue
  where target = 'r/55555555-5555-5555-5555-555555555555/')), 1, 'complete');
select is((select count(*)::integer from public.storage_purge_queue where user_id = '55555555-5555-5555-5555-555555555555'), 2,
  'completing a prefix keeps entries due later (a late sweep must still run)');
select is((select count(*)::integer from public.storage_purge_queue where user_id = '66666666-6666-6666-6666-666666666666'), 1,
  'another user''s entry is untouched');
delete from public.storage_purge_queue;

-- ---------------------------------------------------------------- M1: clip length and prompt pins
select throws_ok($$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"a","tier":"preview","duration":30}', 5, 'dur-key-30') $$,
  '22023', 'invalid duration', 'a 30 s clip is refused at the flat price');
select throws_ok($$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"a","tier":"preview","duration":"10"}', 5, 'dur-key-str') $$,
  '22023', 'invalid duration', 'a non-numeric duration is refused');
select throws_ok($$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"a slow 30 second orbit","tier":"preview"}', 5, 'dur-key-pin') $$,
  '22023', 'prompt_format', 'a 30 s pin in the prompt is refused (the director lets it beat params.duration)');
select throws_ok($$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"orbit at 60 fps","tier":"preview"}', 5, 'dur-key-fps') $$,
  '22023', 'prompt_format', 'a 60 fps pin is refused');
select ok(public.render_prompt_format_ok('a 10s orbit') and public.render_prompt_format_ok('12-second reveal')
          and public.render_prompt_format_ok('3 cars, 24 fps, 2.5x zoom') and public.render_prompt_format_ok(null),
  'lengths within 8..12 s, other numbers and 24 fps are fine');
select ok(not public.render_prompt_format_ok('3s teaser') and not public.render_prompt_format_ok('a 15 SECONDS spin'),
  'lengths outside 8..12 s are refused, whatever the case');

-- ---------------------------------------------------------------- M2 + M3: fees and the cancel rule
select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"a","tier":"preview","duration":10}', 5, 'fee-job-1');
update public.render_jobs set runpod_id = 'rp-f1', status = 'running', started_at = now() where idempotency_key = 'fee-job-1';
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-f1'), 'rp-f1', 'failed',
  'bad model', 'GLB_INVALID', false, '{"fault":"input"}', true, 3), 2, 'an input-caused failure keeps its fee');
select is((select array[fee_credits, refunded_credits]::integer[] from public.render_jobs where runpod_id = 'rp-f1'), array[3, 2],
  'fee and refund recorded on the job');
select is((select failure_fault from public.render_jobs where runpod_id = 'rp-f1'), 'input', 'fault recorded');
select is(public.usage_count('55555555-5555-5555-5555-555555555555', 'input_failure'), 1, 'input failure counted');

-- Cancel requested after the start: a concurrent poll's CANCELLED (refund=true) refunds nothing.
select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"b","tier":"preview"}', 5, 'cancel-job-1');
update public.render_jobs set runpod_id = 'rp-c1', status = 'running', started_at = now() where idempotency_key = 'cancel-job-1';
select ok((public.request_render_cancel((select id from public.render_jobs where runpod_id = 'rp-c1'), false)).cancel_after_start,
  'the row''s own start marks the cancel as after-start');
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-c1'), 'rp-c1', 'cancelled',
  'The render was cancelled.', 'RUNPOD_CANCELLED', false, '{}', true), 0,
  'a cancel after the start is never refunded, even when the poll finishes it with refund=true');

-- Cancel before the start: refunded in full.
select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"c","tier":"preview"}', 5, 'cancel-job-2');
update public.render_jobs set runpod_id = 'rp-c2' where idempotency_key = 'cancel-job-2';
select ok(not (public.request_render_cancel((select id from public.render_jobs where runpod_id = 'rp-c2'), false)).cancel_after_start,
  'a queued job''s cancel is before the start');
select is(public.claim_render_poll((select id from public.render_jobs where runpod_id = 'rp-c2'), 0) and
          not public.claim_render_poll((select id from public.render_jobs where runpod_id = 'rp-c2'), 10), true,
  'the poll throttle is claimed once per window');
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-c2'), 'rp-c2', 'cancelled',
  'Cancelled.', 'CANCELLED_BY_USER', false, '{}', true), 5, 'a cancel before the start is refunded');

-- ---------------------------------------------------------------- M2(d) + L8: render caps under the lock
insert into public.usage_events (user_id, kind) select '55555555-5555-5555-5555-555555555555', 'input_failure' from generate_series(1, 4);
select throws_ok($$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"d","tier":"preview"}', 5, 'cap-key-input') $$,
  'P0001', 'rate_limited: input_failures', 'five input-caused failures today stop new renders');
delete from public.usage_events where kind = 'input_failure';
insert into public.usage_events (user_id, kind) select '55555555-5555-5555-5555-555555555555', 'render' from generate_series(1, 50);
select throws_ok($$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"d","tier":"preview"}', 5, 'cap-key-render') $$,
  'P0001', 'rate_limited: renders', 'the daily render cap is enforced inside create_render_job');
select is((select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"c","tier":"preview"}', 5, 'cancel-job-2')).idempotency_key, 'cancel-job-2',
  'a replayed key still returns its job at the cap');

-- ---------------------------------------------------------------- H1: account deletion
-- The route queues the owner's prefixes (now + a late sweep); the cascade then adds nothing per row.
select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555', 'u/55555555-5555-5555-5555-555555555555/', 'account_deleted');
select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555', 'r/55555555-5555-5555-5555-555555555555/', 'account_deleted');
select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555', 'u/55555555-5555-5555-5555-555555555555/', 'account_deleted',
  now() + public.upload_put_window());
select public.enqueue_storage_purge('55555555-5555-5555-5555-555555555555', 'r/55555555-5555-5555-5555-555555555555/', 'account_deleted',
  now() + public.render_put_window('final'));
set local role supabase_auth_admin;
delete from auth.users where id = '55555555-5555-5555-5555-555555555555';
reset role;
select is((select count(*)::integer from public.render_jobs where user_id = '55555555-5555-5555-5555-555555555555'), 0,
  'the account''s jobs cascaded');
select is((select count(*)::integer from public.storage_purge_queue where user_id = '55555555-5555-5555-5555-555555555555'), 4,
  'the queue outlives the account: only the account-level prefixes, no per-row duplicates');

-- ---------------------------------------------------------------- L7: profiles.email follows auth
set local role supabase_auth_admin;
update auth.users set email = 'renamed@example.com' where id = '66666666-6666-6666-6666-666666666666';
reset role;
select is((select email from public.profiles where id = '66666666-6666-6666-6666-666666666666'), 'renamed@example.com',
  'an auth email change reaches profiles.email');

select * from finish();
rollback;
