-- Public share links for finished renders (lane "share", 2026-09-29).
--
-- An owner opts a succeeded render into a public page at /r/<slug>. The slug is random (>= 128 bits,
-- minted by the API route), so a link cannot be guessed. Rules:
--   * RLS on; users read only their own shares. Nobody but the service role writes, and it does so
--     only through create_render_share / revoke_render_share (the API routes call them after
--     requireUser() and after reading the job through the user's own RLS client).
--   * The public page never reads this table directly: public_render_share() is the one read, it is
--     service-role only, and it returns the render's details only while the share is live (not
--     revoked) and the render's outputs still exist (not expired by retention).
--   * One live share per render. Revoking is final for that slug; sharing again mints a new slug.
--   * Share creation is rate limited per user (render_share_hourly_limit() new links per hour).

create or replace function public.render_share_hourly_limit() returns integer
language sql immutable parallel safe
set search_path = ''
as $$ select 20 $$;

create table public.render_shares (
  id          uuid primary key default gen_random_uuid(),
  -- base64url, at least 22 characters (16 random bytes); the route mints 24 (18 bytes).
  slug        text not null unique check (slug ~ '^[A-Za-z0-9_-]{22,64}$'),
  job_id      uuid not null references public.render_jobs (id) on delete cascade,
  user_id     uuid not null references auth.users (id) on delete cascade,
  show_prompt boolean not null default false,
  created_at  timestamptz not null default now(),
  revoked_at  timestamptz,
  view_count  bigint not null default 0 check (view_count >= 0)
);
create unique index render_shares_live_job_idx on public.render_shares (job_id) where revoked_at is null;
create index render_shares_user_created_idx on public.render_shares (user_id, created_at desc);

alter table public.render_shares enable row level security;
revoke all on public.render_shares from anon, authenticated;
grant select on public.render_shares to authenticated;
grant all on public.render_shares to service_role;

create policy render_shares_select_own on public.render_shares
  for select to authenticated using (user_id = (select auth.uid()));

-- True while a job's outputs still exist: succeeded, not swept, and its retention has not run out
-- (the sweep runs every few minutes, so a job can be past retention before expired_at is set).
create or replace function public.render_outputs_live(p_job public.render_jobs) returns boolean
language sql stable
set search_path = ''
as $$
  select p_job.status = 'succeeded'
     and p_job.expired_at is null
     and coalesce(p_job.finished_at, p_job.updated_at) + make_interval(days => p_job.retention_days) > now()
$$;

-- Creates the live share for a render, or returns the existing one with show_prompt updated.
--   'render not found'   (P0002) no such job for this user
--   'not_shareable'      (P0001) the render did not succeed or its outputs have expired
--   'rate_limited: max n'(P0001) too many new links in the last hour
--   invalid slug          (22023)
create or replace function public.create_render_share(
  p_user_id     uuid,
  p_job_id      uuid,
  p_slug        text,
  p_show_prompt boolean
) returns public.render_shares
language plpgsql
set search_path = ''
as $$
declare
  v_job public.render_jobs;
  v_share public.render_shares;
  v_recent integer;
begin
  if p_slug is null or p_slug !~ '^[A-Za-z0-9_-]{22,64}$' then
    raise exception 'invalid slug' using errcode = '22023';
  end if;
  -- Row lock: two concurrent "Share" clicks on one render serialise here and the second one returns the first's link.
  select * into v_job from public.render_jobs where id = p_job_id and user_id = p_user_id for update;
  if not found then
    raise exception 'render not found' using errcode = 'P0002';
  end if;
  if not public.render_outputs_live(v_job) then
    raise exception 'not_shareable' using errcode = 'P0001';
  end if;

  update public.render_shares set show_prompt = coalesce(p_show_prompt, false)
   where job_id = p_job_id and revoked_at is null
  returning * into v_share;
  if found then
    return v_share;
  end if;

  -- Per-user lock so parallel creates on different renders cannot both slip under the limit.
  perform pg_advisory_xact_lock(hashtextextended('render_share:' || p_user_id::text, 0));
  select count(*) into v_recent from public.render_shares
   where user_id = p_user_id and created_at > now() - interval '1 hour';
  if v_recent >= public.render_share_hourly_limit() then
    raise exception 'rate_limited: max %', public.render_share_hourly_limit() using errcode = 'P0001';
  end if;

  insert into public.render_shares (slug, job_id, user_id, show_prompt)
  values (p_slug, p_job_id, p_user_id, coalesce(p_show_prompt, false))
  returning * into v_share;
  return v_share;
end $$;

-- Revokes the render's live share. Returns how many were revoked (0 when it was not shared).
create or replace function public.revoke_render_share(p_user_id uuid, p_job_id uuid) returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  update public.render_shares set revoked_at = now()
   where job_id = p_job_id and user_id = p_user_id and revoked_at is null;
  get diagnostics v_count = row_count;
  return v_count;
end $$;

-- The public read, by slug. `state`: 'live' | 'revoked' | 'expired'; no row for an unknown slug.
-- Render details are returned only when live; the prompt only when the owner chose to show it.
create or replace function public.public_render_share(p_slug text)
returns table (
  state       text,
  job_id      uuid,
  user_id     uuid,
  kind        public.render_job_kind,
  prompt      text,
  aspect      text,
  width       integer,
  height      integer,
  finished_at timestamptz
)
language sql stable
set search_path = ''
as $$
  select case when s.revoked_at is not null then 'revoked'
              when not public.render_outputs_live(j) then 'expired'
              else 'live' end,
         l.job_id, l.user_id, l.kind, l.prompt, l.aspect, l.width, l.height, l.finished_at
    from public.render_shares s
    join public.render_jobs j on j.id = s.job_id
    left join lateral (
      select j.id as job_id, j.user_id, j.kind,
             case when s.show_prompt then nullif(j.params ->> 'prompt', '') end as prompt,
             j.params ->> 'aspect' as aspect,
             case when jsonb_typeof(j.video -> 'width') = 'number' then (j.video ->> 'width')::numeric::integer end as width,
             case when jsonb_typeof(j.video -> 'height') = 'number' then (j.video ->> 'height')::numeric::integer end as height,
             j.finished_at
       where s.revoked_at is null and public.render_outputs_live(j)
    ) l on true
   where p_slug ~ '^[A-Za-z0-9_-]{22,64}$' and s.slug = p_slug
$$;

-- Best-effort view counter for a live share.
create or replace function public.bump_render_share_view(p_slug text) returns void
language sql
set search_path = ''
as $$
  update public.render_shares set view_count = view_count + 1 where slug = p_slug and revoked_at is null
$$;

revoke execute on function public.render_share_hourly_limit(), public.render_outputs_live(public.render_jobs),
  public.create_render_share(uuid, uuid, text, boolean), public.revoke_render_share(uuid, uuid),
  public.public_render_share(text), public.bump_render_share_view(text)
  from public, anon, authenticated;
grant execute on function public.render_share_hourly_limit(), public.render_outputs_live(public.render_jobs),
  public.create_render_share(uuid, uuid, text, boolean), public.revoke_render_share(uuid, uuid),
  public.public_render_share(text), public.bump_render_share_view(text)
  to service_role;
