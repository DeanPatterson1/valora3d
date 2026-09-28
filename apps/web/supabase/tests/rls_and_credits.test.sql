-- pgTAP: RLS isolation and the credit functions.
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(24);

-- Two users. Inserting into auth.users fires handle_new_user (profile + 50-credit grant).
insert into auth.users (id, email, raw_user_meta_data)
values ('11111111-1111-1111-1111-111111111111', 'a@example.com', '{"name":"Ann"}'),
       ('22222222-2222-2222-2222-222222222222', 'b@example.com', '{}');

select is((select count(*)::int from public.profiles), 2, 'trigger creates a profile per user');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), public.free_plan_credits(),
          'new user starts with the Free plan credits');
select is(public.free_plan_credits(), 50, 'Free plan grant is 50 credits');

-- Every public table has RLS on.
select is(
  (select count(*)::int from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity),
  0, 'RLS enabled on every public table');

-- Service-role side: a project for each user, a version, a ready upload.
insert into public.projects (id, user_id, name) values
  ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'A car'),
  ('bbbbbbbb-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', 'B car');
insert into public.uploads (id, user_id, project_id, file_name, r2_key, size_bytes, status) values
  ('aaaaaaaa-1111-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
   'aaaaaaaa-0000-0000-0000-000000000001', 'car.glb',
   'u/11111111-1111-1111-1111-111111111111/x.glb', 1024, 'ready');

select throws_ok(
  $$ insert into public.uploads (user_id, file_name, r2_key, size_bytes)
     values ('11111111-1111-1111-1111-111111111111', 'x.glb', 'u/22222222-2222-2222-2222-222222222222/x.glb', 1) $$,
  '23514', null, 'an upload key must sit under its owner prefix');
select throws_ok(
  $$ insert into public.uploads (user_id, file_name, format, r2_key, size_bytes)
     values ('11111111-1111-1111-1111-111111111111', 'x.fbx', 'fbx', 'u/11111111-1111-1111-1111-111111111111/y.fbx', 1) $$,
  '23514', null, 'uploads are .glb only');
select throws_ok(
  $$ insert into public.uploads (user_id, file_name, r2_key, size_bytes)
     values ('11111111-1111-1111-1111-111111111111', 'x.glb', 'u/11111111-1111-1111-1111-111111111111/z.glb', 209715201) $$,
  '23514', null, 'uploads over 200 MB are refused');

-- create_render_job: debits atomically, idempotent, refuses overdraft.
select lives_ok(
  $$ select public.create_render_job('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
       null, 'aaaaaaaa-1111-0000-0000-000000000001', 'final', '{}'::jsonb, 30, 'key-00000001') $$,
  'create_render_job with enough credits');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 20, 'job cost debited');
select lives_ok(
  $$ select public.create_render_job('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
       null, null, 'final', '{}'::jsonb, 30, 'key-00000001') $$,
  'retry with the same idempotency key');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 20, 'retry is not charged twice');
select throws_ok(
  $$ select public.create_render_job('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
       null, null, 'final', '{}'::jsonb, 30, 'key-00000002') $$,
  'P0001', null, 'overdraft refused');
select is((select count(*)::int from public.render_jobs), 1, 'refused job leaves no row');
select throws_ok(
  $$ select public.create_render_job('11111111-1111-1111-1111-111111111111', 'bbbbbbbb-0000-0000-0000-000000000001',
       null, null, 'final', '{}'::jsonb, 1, 'key-00000003') $$,
  'P0002', null, 'cannot render into another user''s project');

-- refund_render_job: only failed/cancelled, once.
select throws_ok(
  $$ select public.refund_render_job((select id from public.render_jobs limit 1)) $$,
  '22023', null, 'a queued job is not refundable');
update public.render_jobs set status = 'failed';
select is(public.refund_render_job((select id from public.render_jobs limit 1)), 30, 'failed job refunded');
select is(public.refund_render_job((select id from public.render_jobs limit 1)), 0, 'second refund is a no-op');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 50, 'balance restored');

-- The ledger is append-only.
select throws_ok($$ update public.credit_ledger set amount = 9999 $$, '42501', null, 'ledger rows cannot be edited');

-- RLS as user A.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);

select is((select count(*)::int from public.projects), 1, 'A sees only A''s projects');
select is((select count(*)::int from public.credit_ledger where user_id <> '11111111-1111-1111-1111-111111111111'), 0,
          'A sees none of B''s ledger');
select throws_ok(
  $$ insert into public.credit_ledger (user_id, amount, reason, ref)
     values ('11111111-1111-1111-1111-111111111111', 1000, 'pack_purchase', 'forged') $$,
  '42501', null, 'a user cannot grant themselves credits');
select throws_ok(
  $$ select public.create_render_job('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
       null, null, 'final', '{}'::jsonb, 0, 'key-00000009') $$,
  '42501', null, 'users cannot call create_render_job');
select throws_ok($$ update public.profiles set plan = 'pro' $$, '42501', null, 'a user cannot change their plan');

select * from finish();
rollback;
