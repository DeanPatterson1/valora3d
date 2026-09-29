-- pgTAP: the render pipeline migration (finish_render_job, render_job_private).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(12);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at)
values ('44444444-4444-4444-4444-444444444444', 'render@example.com', now());
reset role;

insert into public.projects (id, user_id, name)
values ('dddddddd-0000-0000-0000-000000000001', '44444444-4444-4444-4444-444444444444', 'Render car');

-- Two preview jobs of 10 credits each, one after the other (Free renders one at a time).
select public.create_render_job('44444444-4444-4444-4444-444444444444', 'dddddddd-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"a","tier":"preview"}', 10, 'job-key-one-1');
update public.render_jobs set runpod_id = 'rp-1', status = 'running' where idempotency_key = 'job-key-one-1';

-- Success: outputs recorded, nothing refunded.
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-1'), 'rp-1', 'succeeded',
  null, null, null, '{"outputs":{"video":{"bytes":10}},"gpu_seconds":571.9,"output_keys":["r/x/video.mp4"]}', false), 0,
  'success moves the job and refunds nothing');

select public.create_render_job('44444444-4444-4444-4444-444444444444', 'dddddddd-0000-0000-0000-000000000001',
  null, null, 'preview', '{"prompt":"b","tier":"preview"}', 10, 'job-key-two-2');
select is(public.user_balance('44444444-4444-4444-4444-444444444444'), 10, 'two renders debited');
update public.render_jobs set runpod_id = 'rp-2' where idempotency_key = 'job-key-two-2';
select is((select status::text from public.render_jobs where runpod_id = 'rp-1'), 'succeeded', 'job succeeded');
select is((select output_keys from public.render_jobs where runpod_id = 'rp-1'), array['r/x/video.mp4'], 'output keys stored');
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-1'), 'rp-1', 'failed',
  'x', 'INTERNAL', true, '{}', true), -1, 'a late failure after success changes nothing');

-- Failure: refunded once, on the same attempt only.
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-2'), 'rp-other', 'failed',
  'x', 'RENDER_FAILED', true, '{}', true), -1, 'another attempt''s report is ignored');
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-2'), 'rp-2', 'failed',
  'The render failed.', 'RENDER_FAILED', true, '{}', true), 10, 'failure refunds the debit');
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-2'), 'rp-2', 'failed',
  'The render failed.', 'RENDER_FAILED', true, '{}', true), -1, 'a duplicate webhook refunds nothing');
select is(public.user_balance('44444444-4444-4444-4444-444444444444'), 20, 'balance after one success and one refund');
select throws_ok(
  $$ select public.finish_render_job(gen_random_uuid(), null, 'succeeded', null, null, null, '{}', true) $$,
  '22023', null, 'a success is never refunded');

-- Users can neither read the private table nor call the function.
insert into public.render_job_private (job_id, webhook_token_hash)
values ((select id from public.render_jobs where runpod_id = 'rp-2'), repeat('a', 64));
set local role authenticated;
set local request.jwt.claims to '{"sub":"44444444-4444-4444-4444-444444444444","role":"authenticated"}';
select throws_ok($$ select count(*) from public.render_job_private $$, '42501', null, 'users cannot read render_job_private');
select throws_ok(
  $$ select public.finish_render_job(gen_random_uuid(), null, 'failed', null, null, null, '{}', true) $$,
  '42501', null, 'users cannot call finish_render_job');
reset role;

select * from finish();
rollback;
