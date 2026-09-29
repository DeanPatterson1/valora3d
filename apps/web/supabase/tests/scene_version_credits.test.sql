-- pgTAP: saving a scene version is a server operation that charges it (20260929100000_scene_version_credits.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(34);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at)
values ('11111111-1111-1111-1111-111111111111', 'sv-a@example.com', now()),
       ('22222222-2222-2222-2222-222222222222', 'sv-b@example.com', now());
reset role;

insert into public.projects (id, user_id, name) values
  ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'A car'),
  ('aaaaaaaa-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 'A second car'),
  ('bbbbbbbb-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', 'B car');

-- Prices mirror CREDIT_COSTS (lib/pricing.test.ts pins both sides).
select is(public.scene_action_cost('generate'), 5, 'a generation costs 5');
select is(public.scene_action_cost('edit'), 2, 'a prompt edit costs 2');
select is(public.scene_action_cost('adjust'), 0, 'a slider adjustment is free');
select is(public.scene_action_cost('free'), null, 'an unknown action has no price');

-- ---------------------------------------------------------------------------------------------
-- Grants: the API is the only write path.
-- ---------------------------------------------------------------------------------------------
select ok(not has_table_privilege('authenticated', 'public.scene_versions', 'INSERT'), 'users cannot insert versions');
select ok(not has_table_privilege('authenticated', 'public.scene_versions', 'UPDATE'), 'users cannot update versions');
select ok(not has_table_privilege('authenticated', 'public.scene_versions', 'DELETE'), 'users cannot delete versions');
select ok(has_table_privilege('authenticated', 'public.scene_versions', 'SELECT'), 'users still read their versions');
select ok(not has_function_privilege('authenticated', 'public.save_scene_version(uuid, uuid, uuid, text, jsonb, text, text)', 'EXECUTE'),
          'users cannot call save_scene_version');
select ok(not has_function_privilege('anon', 'public.save_scene_version(uuid, uuid, uuid, text, jsonb, text, text)', 'EXECUTE'),
          'anon cannot call save_scene_version');
select ok(has_function_privilege('service_role', 'public.save_scene_version(uuid, uuid, uuid, text, jsonb, text, text)', 'EXECUTE'),
          'the service role can');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select throws_ok(
  $$ insert into public.scene_versions (project_id, user_id, index, plan)
     values ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 0, '{}') $$,
  '42501', null, 'a direct insert as the user is refused');
select throws_ok(
  $$ select public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
       null, 'x', '{}'::jsonb, 'adjust', 'user-key-0001') $$,
  '42501', null, 'the user cannot call the function either');
reset role;

-- ---------------------------------------------------------------------------------------------
-- Debit + insert, atomically, with the action resolved by the server.
-- ---------------------------------------------------------------------------------------------
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 10, 'A starts with the Free credits');

select is(
  (public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
     null, 'night', '{"v":1}'::jsonb, 'adjust', 'key-first-001') ->> 'charged')::int,
  5, 'the first version is charged as a generation whatever was declared');
select is((select action from public.scene_versions where idempotency_key = 'key-first-001'), 'generate',
          'and recorded as one');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 5, 'balance debited');
select is((select count(*)::int from public.credit_ledger
            where ref = 'version:' || (select id from public.scene_versions where idempotency_key = 'key-first-001')::text
              and reason = 'scene_generation' and amount = -5), 1, 'one scene_generation ledger row, ref version:<id>');

select is(
  (public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
     (select id from public.scene_versions where idempotency_key = 'key-first-001'), 'rain', '{"v":2}'::jsonb, 'edit', 'key-edit-0001')
     -> 'version' ->> 'index')::int,
  1, 'an edit gets the next index');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 3, 'an edit costs 2');
select is(
  (public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
     (select id from public.scene_versions where idempotency_key = 'key-first-001'), 'manual: fog', '{"v":3}'::jsonb, 'adjust', 'key-adjust-01')
     ->> 'charged')::int,
  0, 'an adjustment is free');
select is((select count(*)::int from public.credit_ledger where user_id = '11111111-1111-1111-1111-111111111111' and amount < 0), 2,
          'a free adjustment writes no ledger row');
select throws_ok(
  $$ select public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
       null, 'x', '{"v":4}'::jsonb, 'edit', 'key-noparent1') $$,
  '22023', null, 'an edit needs the version it changes');
select throws_ok(
  $$ select public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000002',
       (select id from public.scene_versions where idempotency_key = 'key-first-001'), 'x', '{"v":4}'::jsonb, 'generate', 'key-xparent01') $$,
  'P0002', null, 'a parent from another project is refused');
select throws_ok(
  $$ select public.save_scene_version('11111111-1111-1111-1111-111111111111', 'bbbbbbbb-0000-0000-0000-000000000001',
       null, 'x', '{"v":4}'::jsonb, 'generate', 'key-foreign01') $$,
  'P0002', null, 'cannot save into another user''s project');

-- ---------------------------------------------------------------------------------------------
-- Idempotency.
-- ---------------------------------------------------------------------------------------------
select is(
  (public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
     (select id from public.scene_versions where idempotency_key = 'key-first-001'), 'rain', '{"v":2}'::jsonb, 'edit', 'key-edit-0001')
     ->> 'replay')::boolean,
  true, 'a retried save is a replay');
select is(public.user_balance('11111111-1111-1111-1111-111111111111'), 3, 'the replay is not charged again');
select is((select count(*)::int from public.scene_versions where project_id = 'aaaaaaaa-0000-0000-0000-000000000001'), 3,
          'the replay inserts nothing');
select throws_ok(
  $$ select public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001',
       null, 'rain', '{"v":99}'::jsonb, 'edit', 'key-edit-0001') $$,
  '23505', null, 'a key cannot be reused for a different version');

-- ---------------------------------------------------------------------------------------------
-- Insufficient and negative balances.
-- ---------------------------------------------------------------------------------------------
insert into public.credit_ledger (user_id, amount, reason, ref)
values ('22222222-2222-2222-2222-222222222222', -9, 'admin_adjustment', 'test:b:drain');
select throws_ok(
  $$ select public.save_scene_version('22222222-2222-2222-2222-222222222222', 'bbbbbbbb-0000-0000-0000-000000000001',
       null, 'x', '{"v":1}'::jsonb, 'generate', 'key-b-short01') $$,
  'P0001', 'insufficient_credits: need 5, have 1', 'a generation with 1 credit is refused');
select is((select count(*)::int from public.scene_versions where user_id = '22222222-2222-2222-2222-222222222222'), 0,
          'a refused save leaves no version');
insert into public.credit_ledger (user_id, amount, reason, ref)
values ('22222222-2222-2222-2222-222222222222', 9, 'admin_adjustment', 'test:b:top');
select lives_ok(
  $$ select public.save_scene_version('22222222-2222-2222-2222-222222222222', 'bbbbbbbb-0000-0000-0000-000000000001',
       null, 'x', '{"v":1}'::jsonb, 'generate', 'key-b-ok-0001') $$, 'with credits it saves');
insert into public.credit_ledger (user_id, amount, reason, ref)
values ('22222222-2222-2222-2222-222222222222', -20, 'billing_reversal', 'test:b:chargeback');
select throws_ok(
  $$ select public.save_scene_version('22222222-2222-2222-2222-222222222222', 'bbbbbbbb-0000-0000-0000-000000000001',
       (select id from public.scene_versions where idempotency_key = 'key-b-ok-0001'), 'fog', '{"v":2}'::jsonb, 'adjust', 'key-b-neg-001') $$,
  'P0001', 'insufficient_credits: need 0, have -15', 'a negative balance blocks even a free adjustment');

-- ---------------------------------------------------------------------------------------------
-- Hourly rate limit.
-- ---------------------------------------------------------------------------------------------
insert into public.scene_versions (project_id, user_id, index, plan)
select 'aaaaaaaa-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', g, '{}'::jsonb
  from generate_series(0, public.scene_version_hourly_cap() - 4) g;
select throws_ok(
  $$ select public.save_scene_version('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000002',
       null, 'x', '{"v":1}'::jsonb, 'generate', 'key-a-rate-01') $$,
  'P0001', 'rate_limited: max 120 per hour', 'the 121st version in an hour is refused');

select * from finish();
rollback;
