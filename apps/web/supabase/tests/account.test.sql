-- pgTAP: account history view + render-ready mail preference (migration 20260929120000_account.sql).
-- Run locally only: `supabase start` then `supabase test db` (from apps/web). Never against a remote.
begin;
create extension if not exists pgtap with schema extensions;
select plan(14);

set local role supabase_auth_admin;
insert into auth.users (id, email, email_confirmed_at)
values ('11111111-1111-1111-1111-111111111111', 'hist-a@example.com', now()),
       ('22222222-2222-2222-2222-222222222222', 'hist-b@example.com', now());
reset role;

select is((select email_render_ready from public.profiles where id = '11111111-1111-1111-1111-111111111111'), true,
          'render-ready mail is on by default');

-- Service-role side: a monthly grant, a pack, a render debit + its refund for A; a pack for B.
insert into public.projects (id, user_id, name) values
  ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'A car');
insert into public.render_jobs (id, user_id, project_id, kind, status, cost_credits)
values ('cccccccc-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
        'aaaaaaaa-0000-0000-0000-000000000001', 'final', 'failed', 20);
insert into public.credit_ledger (user_id, amount, reason, ref, project_id, job_id) values
  ('11111111-1111-1111-1111-111111111111', 500, 'plan_grant', 'paddle:sub:sub_1:1790000000:creator', null, null),
  ('11111111-1111-1111-1111-111111111111', 100, 'pack_purchase', 'paddle:txn:txn_1', null, null),
  ('11111111-1111-1111-1111-111111111111', -20, 'render_final', 'render:cccccccc-0000-0000-0000-000000000001',
   'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001'),
  ('11111111-1111-1111-1111-111111111111', 20, 'render_refund', 'refund:cccccccc-0000-0000-0000-000000000001',
   'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001'),
  ('22222222-2222-2222-2222-222222222222', 2000, 'pack_purchase', 'paddle:txn:txn_2', null, null);

-- As user A.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);

select is((select count(*)::int from public.credit_history), 5, 'A sees exactly A''s 5 ledger rows');
select is((select count(*)::int from public.credit_history where user_id <> '11111111-1111-1111-1111-111111111111'), 0,
          'A sees none of B''s history');
select is((select balance_after from public.credit_history order by id desc limit 1), 650,
          'the newest row''s running balance is the balance (50 + 500 + 100 - 20 + 20)');
select is((select balance_after from public.credit_history where reason = 'plan_grant'), 550,
          'running balance after the monthly grant');
select is((select plan from public.credit_history where reason = 'plan_grant'), 'creator',
          'a monthly grant names its plan');
select is((select count(*)::int from public.credit_history where plan is not null), 1, 'only plan grants carry a plan');
select is((select job_status::text from public.credit_history where reason = 'render_refund'), 'failed',
          'a refund carries its job status');
select is((select balance_after from public.credit_history order by id desc limit 1 offset 1), 630,
          'a later page still gets the true running balance');
select is((select count(*)::int from information_schema.columns
            where table_schema = 'public' and table_name = 'credit_history' and column_name = 'ref'), 0,
          'the payment ref is not exposed');

update public.profiles set email_render_ready = false where id = '11111111-1111-1111-1111-111111111111';
select is((select email_render_ready from public.profiles), false, 'a user can turn render-ready mail off');
update public.profiles set email_render_ready = false where id = '22222222-2222-2222-2222-222222222222';
reset role;
select is((select email_render_ready from public.profiles where id = '22222222-2222-2222-2222-222222222222'), true,
          'a user cannot change someone else''s preference');

set local role anon;
select throws_ok($$ select * from public.credit_history $$, '42501', null, 'anon cannot read the history');
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"22222222-2222-2222-2222-222222222222","role":"authenticated"}', true);
select is((select balance_after from public.credit_history order by id desc limit 1), 2050, 'B sees B''s own balance');
reset role;

select * from finish();
rollback;
