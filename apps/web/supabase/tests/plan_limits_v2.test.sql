-- pgTAP: plan limits v2, plan enforcement in create_render_job, ledger reasons, watermark, retention
-- (migration 20260928150000_plan_limits_v2.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(40);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at)
values ('55555555-5555-5555-5555-555555555555', 'free@example.com', now()),
       ('66666666-6666-6666-6666-666666666666', 'pro@example.com', now());
reset role;

insert into public.projects (id, user_id, name) values
  ('eeeeeeee-0000-0000-0000-000000000001', '55555555-5555-5555-5555-555555555555', 'Free car'),
  ('eeeeeeee-0000-0000-0000-000000000002', '66666666-6666-6666-6666-666666666666', 'Pro car');

-- Plan limits (mirrored by PLAN_LIMITS in lib/pricing.ts).
select is((select max_resolution || '|' || tiers::text || '|' || watermark || '|' || retention_days || '|' || max_active_jobs
             from public.plan_limits('free')), '540p|{preview}|true|7|1', 'free: 540p previews, watermark, 7 days, 1 at a time');
select is((select max_resolution || '|' || tiers::text || '|' || watermark || '|' || retention_days || '|' || max_active_jobs
             from public.plan_limits('creator')), '1080p|{preview,final}|false|30|1', 'creator: 1080p finals, 30 days');
select is((select max_resolution || '|' || tiers::text || '|' || watermark || '|' || retention_days || '|' || max_active_jobs
             from public.plan_limits('pro')), '1080p|{preview,final}|false|90|3', 'pro: 1080p finals, 90 days, 3 at once');
select is((select count(*)::int from (values ('free'::public.plan_tier), ('creator'), ('pro')) p(plan)
             cross join lateral public.plan_limits(p.plan) l where l.max_resolution not in ('540p', '1080p')), 0,
          'no plan claims a resolution the worker cannot render');

-- Free: previews only, watermarked, 7-day retention, one at a time, debited as render_preview.
select throws_ok(
  $$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
       null, null, 'final', '{"prompt":"","tier":"final"}', 100, 'free-final-key') $$,
  'P0001', 'plan_required: final', 'Free cannot render a final');
select throws_ok(
  $$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
       null, null, 'preview', '{"prompt":"","tier":"preview","watermark":false}', 5, 'free-wm-key-1') $$,
  '22023', null, 'the request can never carry a watermark flag');
select lives_ok(
  $$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
       null, null, 'preview', '{"prompt":"a","tier":"preview"}', 5, 'free-prev-key-1') $$,
  'Free renders a preview');
select is((select watermark::text || '/' || retention_days from public.render_jobs where idempotency_key = 'free-prev-key-1'),
          'true/7', 'the Free job is stamped watermark=true, 7 days');
select is((select reason from public.credit_ledger
            where ref = 'render:' || (select id from public.render_jobs where idempotency_key = 'free-prev-key-1')::text),
          'render_preview', 'a preview debit is recorded as render_preview');
select throws_ok(
  $$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
       null, null, 'preview', '{"prompt":"b","tier":"preview"}', 5, 'free-prev-key-2') $$,
  'P0001', 'too_many_active: max 1', 'Free has one render at a time');
select lives_ok(
  $$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
       null, null, 'preview', '{"prompt":"a","tier":"preview"}', 5, 'free-prev-key-1') $$,
  'a replayed key returns the job before the concurrency limit is counted');
select is(public.user_balance('55555555-5555-5555-5555-555555555555'), 5, 'charged once');

-- The worker's own report of the watermark is stored.
update public.render_jobs set runpod_id = 'rp-free-1', status = 'running' where idempotency_key = 'free-prev-key-1';
select is(public.finish_render_job((select id from public.render_jobs where runpod_id = 'rp-free-1'), 'rp-free-1', 'succeeded',
  null, null, null, '{"watermarked":false,"warnings":["watermark skipped"]}', false), 0, 'the Free job succeeds');
select is((select watermarked from public.render_jobs where runpod_id = 'rp-free-1'), false, 'watermarked=false is recorded as reported');

-- Pro (a live subscription): finals, no watermark, 90 days, three at once, debited as render_final.
insert into public.billing_subscriptions (id, user_id, plan, status, paid_through)
values ('sub_testpro', '66666666-6666-6666-6666-666666666666', 'pro', 'active', now() + interval '30 days');
insert into public.credit_ledger (user_id, amount, reason, ref)
values ('66666666-6666-6666-6666-666666666666', 500, 'admin_adjustment', 'test:v2:topup');
select lives_ok(
  $$ select public.create_render_job('66666666-6666-6666-6666-666666666666', 'eeeeeeee-0000-0000-0000-000000000002',
       null, null, 'final', '{"prompt":"p1","tier":"final"}', 100, 'pro-final-key-1') $$,
  'Pro renders a final');
select is((select watermark::text || '/' || retention_days from public.render_jobs where idempotency_key = 'pro-final-key-1'),
          'false/90', 'the Pro job is stamped watermark=false, 90 days');
select is((select reason from public.credit_ledger
            where ref = 'render:' || (select id from public.render_jobs where idempotency_key = 'pro-final-key-1')::text),
          'render_final', 'a final debit is recorded as render_final');
select lives_ok(
  $$ select public.create_render_job('66666666-6666-6666-6666-666666666666', 'eeeeeeee-0000-0000-0000-000000000002',
       null, null, 'final', '{"prompt":"p2","tier":"final"}', 100, 'pro-final-key-2') $$,
  'Pro: second render at once');
select lives_ok(
  $$ select public.create_render_job('66666666-6666-6666-6666-666666666666', 'eeeeeeee-0000-0000-0000-000000000002',
       null, null, 'preview', '{"prompt":"p3","tier":"preview"}', 5, 'pro-prev-key-3') $$,
  'Pro: third render at once');
select throws_ok(
  $$ select public.create_render_job('66666666-6666-6666-6666-666666666666', 'eeeeeeee-0000-0000-0000-000000000002',
       null, null, 'preview', '{"prompt":"p4","tier":"preview"}', 5, 'pro-prev-key-4') $$,
  'P0001', 'too_many_active: max 3', 'Pro: a fourth is refused');

-- Retention of outputs, by the retention stamped at creation.
update public.render_jobs set status = 'succeeded', finished_at = now() - interval '8 days'
 where user_id in ('55555555-5555-5555-5555-555555555555', '66666666-6666-6666-6666-666666666666');
select is((select array_agg(user_id::text) from public.expired_render_outputs(100)),
          array['55555555-5555-5555-5555-555555555555'], 'after 8 days only the 7-day (Free) job is due');
select is(public.mark_render_outputs_expired(array(select job_id from public.expired_render_outputs(100))), 1, 'marked expired');
select is((select count(*)::int from public.render_jobs where expired_at is not null and output_keys = '{}'), 1,
          'the expired job keeps its row, without output keys');
select is((select count(*)::int from public.expired_render_outputs(100)), 0, 'nothing left to expire');
select is(public.mark_render_outputs_expired(array(select id from public.render_jobs where expired_at is not null)), 0,
          'marking again changes nothing');
update public.render_jobs set finished_at = now() - interval '91 days' where user_id = '66666666-6666-6666-6666-666666666666';
select is((select count(*)::int from public.expired_render_outputs(2)), 2, 'Pro jobs expire after 90 days, in batches');

-- Retention of uploaded models: the owner's current plan, from the last use; never while rendering.
insert into public.uploads (id, user_id, project_id, file_name, r2_key, size_bytes, status, created_at, completed_at) values
  ('eeeeeeee-1111-0000-0000-000000000001', '55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
   'old.glb', 'u/55555555-5555-5555-5555-555555555555/old.glb', 10, 'ready', now() - interval '10 days', now() - interval '10 days'),
  ('eeeeeeee-1111-0000-0000-000000000002', '55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
   'used.glb', 'u/55555555-5555-5555-5555-555555555555/used.glb', 10, 'ready', now() - interval '10 days', now() - interval '10 days'),
  ('eeeeeeee-1111-0000-0000-000000000003', '55555555-5555-5555-5555-555555555555', null,
   'abandoned.glb', 'u/55555555-5555-5555-5555-555555555555/abandoned.glb', 10, 'pending', now() - interval '2 days', null),
  ('eeeeeeee-1111-0000-0000-000000000004', '66666666-6666-6666-6666-666666666666', 'eeeeeeee-0000-0000-0000-000000000002',
   'pro.glb', 'u/66666666-6666-6666-6666-666666666666/pro.glb', 10, 'ready', now() - interval '10 days', now() - interval '10 days'),
  ('eeeeeeee-1111-0000-0000-000000000005', '55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
   'busy.glb', 'u/55555555-5555-5555-5555-555555555555/busy.glb', 10, 'ready', now() - interval '10 days', now() - interval '10 days');
-- used.glb was rendered from 2 days ago; busy.glb has a render in flight.
insert into public.render_jobs (user_id, project_id, upload_id, kind, status, cost_credits, created_at, finished_at, retention_days) values
  ('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001', 'eeeeeeee-1111-0000-0000-000000000002',
   'preview', 'succeeded', 0, now() - interval '2 days', now() - interval '2 days', 7),
  ('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001', 'eeeeeeee-1111-0000-0000-000000000005',
   'preview', 'queued', 0, now() - interval '9 days', null, 7);
select is((select array_agg(r2_key order by r2_key) from public.expire_uploads(100)),
          array['u/55555555-5555-5555-5555-555555555555/abandoned.glb', 'u/55555555-5555-5555-5555-555555555555/old.glb'],
          'expire_uploads claims the stale Free model and the abandoned upload only');
select is((select status::text || '/' || reject_reason from public.uploads where id = 'eeeeeeee-1111-0000-0000-000000000001'),
          'rejected/expired', 'a claimed model is rejected as expired');
select throws_ok(
  $$ select public.create_render_job('55555555-5555-5555-5555-555555555555', 'eeeeeeee-0000-0000-0000-000000000001',
       null, 'eeeeeeee-1111-0000-0000-000000000001', 'preview', '{"prompt":"x","tier":"preview"}', 5, 'free-expired-model') $$,
  'P0002', null, 'an expired model cannot be rendered');
select is((select count(*)::int from public.expire_uploads(100)), 2, 'a claim whose delete is still pending is returned again');
select is(public.mark_uploads_purged(array['eeeeeeee-1111-0000-0000-000000000001', 'eeeeeeee-1111-0000-0000-000000000003']::uuid[]), 2,
          'purged after the R2 delete');
select is((select count(*)::int from public.expire_uploads(100)), 0, 'nothing left to delete');
select is(public.mark_uploads_purged(array['eeeeeeee-1111-0000-0000-000000000001']::uuid[]), 0, 'purging again changes nothing');

-- A lapsed Pro plan keeps Pro's model retention for 30 days after its paid period (dunning grace).
update public.billing_subscriptions set status = 'canceled', paid_through = now() - interval '5 days' where id = 'sub_testpro';
select is(public.user_plan('66666666-6666-6666-6666-666666666666'), 'free'::public.plan_tier, 'the lapsed Pro user is on Free');
select is((select count(*)::int from public.expire_uploads(100) e where e.user_id = '66666666-6666-6666-6666-666666666666'), 0,
          'but their 10-day-old model is not deleted during the grace period');
-- Rendering from a model marks it used (under a row lock the sweep respects).
select lives_ok(
  $$ select public.create_render_job('66666666-6666-6666-6666-666666666666', 'eeeeeeee-0000-0000-0000-000000000002',
       null, 'eeeeeeee-1111-0000-0000-000000000004', 'preview', '{"prompt":"u","tier":"preview"}', 5, 'pro-used-model') $$,
  'a render from a live model is created');
select isnt((select last_used_at from public.uploads where id = 'eeeeeeee-1111-0000-0000-000000000004'), null,
            'create_render_job records the model as used');

-- Users can call none of it.
set local role authenticated;
set local request.jwt.claims to '{"sub":"55555555-5555-5555-5555-555555555555","role":"authenticated"}';
select throws_ok($$ select * from public.expired_render_outputs(10) $$, '42501', null, 'users cannot list expired outputs');
select throws_ok($$ select * from public.expire_uploads(10) $$, '42501', null, 'users cannot expire uploads');
select throws_ok($$ select * from public.user_plan_limits('55555555-5555-5555-5555-555555555555') $$, '42501', null,
                 'users cannot read another account''s entitlement');
reset role;

select * from finish();
rollback;
