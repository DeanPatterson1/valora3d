-- Valora3D account lane (2026-09-29): usage & billing history, render-ready mail preference.
--
--   * profiles.email_render_ready: the "Email me when a render is ready" toggle in Settings. The
--     owner may change it (column-level UPDATE grant, same RLS policy as name/prefs); lib/server/notify.ts
--     reads it with the service role and sends nothing when it is false.
--   * credit_history: the ledger as the Profile page shows it, with the running balance after each
--     row. security_invoker, so the caller's RLS on credit_ledger (and render_jobs, for the job status)
--     applies BEFORE the window sum: a user only ever sums and sees their own rows. The payment ref is
--     not exposed; only the plan name a monthly grant was for.
--   * No new tables, no SECURITY DEFINER.

alter table public.profiles
  add column email_render_ready boolean not null default true;

grant update (email_render_ready) on public.profiles to authenticated;

create view public.credit_history
with (security_invoker = true) as
  select
    l.id,
    l.user_id,
    l.amount,
    l.reason,
    l.project_id,
    l.job_id,
    l.created_at,
    sum(l.amount) over (partition by l.user_id order by l.id
                        rows between unbounded preceding and current row)::integer as balance_after,
    -- 'paddle:sub:<sub>:<period_end>:<plan>' -> '<plan>' (monthly grants only).
    case when l.reason = 'plan_grant' and l.ref like 'paddle:sub:%'
         then nullif(split_part(l.ref, ':', 5), '') end as plan,
    j.status as job_status,
    j.kind   as job_kind
  from public.credit_ledger l
  left join public.render_jobs j on j.id = l.job_id;

revoke all on public.credit_history from anon, authenticated;
grant select on public.credit_history to authenticated;
grant all on public.credit_history to service_role;
