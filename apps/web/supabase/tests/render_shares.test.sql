-- pgTAP: public share links (migration 20260929130000_render_shares.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(34);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at)
values ('77777777-7777-7777-7777-777777777777', 'owner@example.com', now()),
       ('88888888-8888-8888-8888-888888888888', 'other@example.com', now());
reset role;

insert into public.projects (id, user_id, name) values
  ('dddddddd-0000-0000-0000-000000000001', '77777777-7777-7777-7777-777777777777', 'Owner car'),
  ('dddddddd-0000-0000-0000-000000000002', '88888888-8888-8888-8888-888888888888', 'Other car');

-- j1 succeeded (shareable), j2 still running, j3 swept by retention, j4 past retention but not swept yet,
-- j5 belongs to the other user.
insert into public.render_jobs (id, user_id, project_id, kind, status, params, cost_credits, finished_at, retention_days, expired_at, video)
values
  ('dddddddd-1111-0000-0000-000000000001', '77777777-7777-7777-7777-777777777777', 'dddddddd-0000-0000-0000-000000000001',
   'preview', 'succeeded', '{"prompt":"red car at dusk","tier":"preview","aspect":"9:16"}', 5, now() - interval '1 day', 7, null,
   '{"width":540,"height":960,"fps":30}'),
  ('dddddddd-1111-0000-0000-000000000002', '77777777-7777-7777-7777-777777777777', 'dddddddd-0000-0000-0000-000000000001',
   'preview', 'running', '{"prompt":"x","tier":"preview"}', 5, null, 7, null, null),
  ('dddddddd-1111-0000-0000-000000000003', '77777777-7777-7777-7777-777777777777', 'dddddddd-0000-0000-0000-000000000001',
   'preview', 'succeeded', '{"prompt":"y","tier":"preview"}', 5, now() - interval '9 days', 7, now(), null),
  ('dddddddd-1111-0000-0000-000000000004', '77777777-7777-7777-7777-777777777777', 'dddddddd-0000-0000-0000-000000000001',
   'preview', 'succeeded', '{"prompt":"z","tier":"preview"}', 5, now() - interval '8 days', 7, null, null),
  ('dddddddd-1111-0000-0000-000000000005', '88888888-8888-8888-8888-888888888888', 'dddddddd-0000-0000-0000-000000000002',
   'preview', 'succeeded', '{"prompt":"secret","tier":"preview"}', 5, now() - interval '1 day', 7, null, null);

-- Creation rules.
select throws_ok(
  $$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001', 'short', false) $$,
  '22023', null, 'a short slug is refused');
select throws_ok(
  $$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001', 'aaaaaaaaaaaaaaaaaaaaaa/b', false) $$,
  '22023', null, 'a slug outside base64url is refused');
select throws_ok(
  $$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000005', 'AAAAAAAAAAAAAAAAAAAAAAAA', false) $$,
  'P0002', 'render not found', 'nobody can share another user''s render');
select throws_ok(
  $$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000002', 'BBBBBBBBBBBBBBBBBBBBBBBB', false) $$,
  'P0001', 'not_shareable', 'a running render cannot be shared');
select throws_ok(
  $$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000003', 'CCCCCCCCCCCCCCCCCCCCCCCC', false) $$,
  'P0001', 'not_shareable', 'an expired render cannot be shared');
select throws_ok(
  $$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000004', 'DDDDDDDDDDDDDDDDDDDDDDDD', false) $$,
  'P0001', 'not_shareable', 'a render past retention cannot be shared before the sweep runs');

select is((public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001',
             'share1share1share1share1', false)).slug, 'share1share1share1share1', 'the owner shares a finished render');
select is((public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001',
             'share2share2share2share2', true)).slug, 'share1share1share1share1', 'sharing again returns the live link');
select is((select show_prompt from public.render_shares where slug = 'share1share1share1share1'), true,
          'sharing again updates show_prompt');
select is((select count(*)::int from public.render_shares where job_id = 'dddddddd-1111-0000-0000-000000000001'), 1,
          'one live share per render');

-- Public read.
select is((select state from public.public_render_share('share1share1share1share1')), 'live', 'a live share reads live');
select is((select prompt from public.public_render_share('share1share1share1share1')), 'red car at dusk', 'the prompt shows when ticked');
select is((select width || 'x' || height || ' ' || aspect from public.public_render_share('share1share1share1share1')),
          '540x960 9:16', 'the video size and aspect come through');
select is((select user_id from public.public_render_share('share1share1share1share1')), '77777777-7777-7777-7777-777777777777'::uuid,
          'the owner id comes through for the storage key');
select is((select count(*)::int from public.public_render_share('nosuchslugnosuchslugnosuch')), 0, 'an unknown slug has no row');
select is((select count(*)::int from public.public_render_share('x'' or ''1''=''1')), 0, 'a malformed slug has no row');

select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001',
       'share1share1share1share1', false);
select is((select prompt from public.public_render_share('share1share1share1share1')), null, 'the prompt hides when unticked');

-- View counter.
select public.bump_render_share_view('share1share1share1share1');
select public.bump_render_share_view('share1share1share1share1');
select is((select view_count::int from public.render_shares where slug = 'share1share1share1share1'), 2, 'views are counted');

-- RLS: the owner reads their own shares; the other user reads none; nobody writes or calls the functions.
set local role authenticated;
set local request.jwt.claims to '{"sub":"77777777-7777-7777-7777-777777777777","role":"authenticated"}';
select is((select count(*)::int from public.render_shares), 1, 'the owner sees their share');
select throws_ok($$ update public.render_shares set revoked_at = null $$, '42501', null, 'users cannot update shares');
select throws_ok($$ insert into public.render_shares (slug, job_id, user_id) values ('EEEEEEEEEEEEEEEEEEEEEEEE',
  'dddddddd-1111-0000-0000-000000000001', '77777777-7777-7777-7777-777777777777') $$, '42501', null, 'users cannot insert shares');
select throws_ok($$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001',
  'FFFFFFFFFFFFFFFFFFFFFFFF', false) $$, '42501', null, 'users cannot call create_render_share');
select throws_ok($$ select * from public.public_render_share('share1share1share1share1') $$, '42501', null,
                 'users cannot call the public read directly');
select throws_ok($$ select public.bump_render_share_view('share1share1share1share1') $$, '42501', null,
                 'users cannot bump view counts');
set local request.jwt.claims to '{"sub":"88888888-8888-8888-8888-888888888888","role":"authenticated"}';
select is((select count(*)::int from public.render_shares), 0, 'another user sees no shares');
reset role;
set local role anon;
select throws_ok($$ select * from public.render_shares $$, '42501', null, 'anon cannot read shares');
reset role;

-- Revoke.
select is(public.revoke_render_share('88888888-8888-8888-8888-888888888888', 'dddddddd-1111-0000-0000-000000000001'), 0,
          'another user cannot revoke the share');
select is(public.revoke_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001'), 1,
          'the owner revokes the share');
select is((select state || '/' || coalesce(job_id::text, 'none') from public.public_render_share('share1share1share1share1')),
          'revoked/none', 'a revoked share reads revoked, with no render details');
select public.bump_render_share_view('share1share1share1share1');
select is((select view_count::int from public.render_shares where slug = 'share1share1share1share1'), 2, 'a revoked share counts no views');
select is((public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001',
             'share3share3share3share3', false)).slug, 'share3share3share3share3', 'sharing after revoking mints a new link');

-- Expiry after sharing: the share reads expired, with no details.
update public.render_jobs set expired_at = now() where id = 'dddddddd-1111-0000-0000-000000000001';
select is((select state || '/' || coalesce(job_id::text, 'none') from public.public_render_share('share3share3share3share3')),
          'expired/none', 'a share whose render expired reads expired');

-- Rate limit: 20 new links per hour per user.
update public.render_jobs set expired_at = null where id = 'dddddddd-1111-0000-0000-000000000001';
insert into public.render_shares (slug, job_id, user_id, created_at, revoked_at)
select 'bulk' || lpad(g::text, 20, '0'), 'dddddddd-1111-0000-0000-000000000001', '77777777-7777-7777-7777-777777777777',
       now() - interval '5 minutes', now()
  from generate_series(1, 18) g;
update public.render_shares set revoked_at = now() where slug = 'share3share3share3share3';
select throws_ok(
  $$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001',
       'share4share4share4share4', false) $$,
  'P0001', 'rate_limited: max 20', 'the 21st new link within an hour is refused');
update public.render_shares set created_at = now() - interval '2 hours' where slug like 'bulk%';
select lives_ok(
  $$ select public.create_render_share('77777777-7777-7777-7777-777777777777', 'dddddddd-1111-0000-0000-000000000001',
       'share4share4share4share4', false) $$,
  'older links do not count toward the limit');

select * from finish();
rollback;
