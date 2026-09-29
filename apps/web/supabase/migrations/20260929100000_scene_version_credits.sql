-- Valora3D scene-version credits (credits lane, 2026-09-29).
--
-- Saving a scene version is a server operation: POST /api/projects/:id/versions validates the plan and calls
-- save_scene_version() once, which charges the action and inserts the version in ONE transaction, under the
-- per-user credit lock (like create_render_job). Before this, the browser inserted versions itself and the
-- 2/1-credit debit was a separate, honour-system call.
--   * The price comes from scene_action_cost(action) (mirrors CREDIT_COSTS in lib/pricing.ts; lib/pricing.test.ts
--     pins both). The browser declares an action, never an amount; the FIRST version of a project is always a
--     'generate', whatever was declared.
--   * Idempotent on (user, idempotency_key): a retried save returns the saved version, charged once.
--   * A balance below the price, or any negative balance, refuses (402 at the API), free adjustments included.
--   * At most scene_version_hourly_cap() versions per user per rolling hour (429 at the API).
--   * authenticated loses INSERT/UPDATE/DELETE on scene_versions: the API is the only write path.
-- Rules from the init migration hold: RLS on, service role only for writes, SECURITY INVOKER, search_path ''.

-- ---------------------------------------------------------------------------------------------
-- Constants
-- ---------------------------------------------------------------------------------------------

-- Credits per scene-version action. Mirrors CREDIT_COSTS (scene_generation, prompt_edit, slider_change) in
-- lib/pricing.ts. 'adjust' is a manual slider / output change; the API only lets it through when the plan differs
-- from its parent in slider fields alone (lib/scene/versionAction.ts). Unknown action -> null (the caller raises).
create or replace function public.scene_action_cost(p_action text) returns integer
language sql immutable parallel safe
set search_path = ''
as $$
  select case p_action when 'generate' then 5 when 'edit' then 2 when 'adjust' then 0 end
$$;

-- Versions one user may save per rolling hour. Mirrors VERSION_HOURLY_CAP in lib/scene/versionAction.ts.
create or replace function public.scene_version_hourly_cap() returns integer
language sql immutable parallel safe
set search_path = ''
as $$ select 120 $$;

-- ---------------------------------------------------------------------------------------------
-- Columns
-- ---------------------------------------------------------------------------------------------

alter table public.scene_versions
  -- What was charged, as the server resolved it. Rows saved before this migration are unknown (null).
  add column action          text check (action is null or action in ('generate', 'edit', 'adjust')),
  add column cost_credits    integer not null default 0 check (cost_credits >= 0),
  -- Client idempotency key: a retried save returns the same version, charged once.
  add column idempotency_key text check (idempotency_key is null or char_length(idempotency_key) between 8 and 128),
  add constraint scene_versions_user_idempotency_key unique (user_id, idempotency_key);

-- The hourly rate-limit scan.
create index scene_versions_user_created_idx on public.scene_versions (user_id, created_at desc);

-- ---------------------------------------------------------------------------------------------
-- Privileges: the API is the only write path.
-- ---------------------------------------------------------------------------------------------

drop policy if exists versions_insert_own on public.scene_versions;
revoke insert, update, delete on public.scene_versions from anon, authenticated;
-- SELECT (versions_select_own) is unchanged.

-- ---------------------------------------------------------------------------------------------
-- save_scene_version
-- ---------------------------------------------------------------------------------------------

-- Charges the action and inserts the version, atomically. Returns
--   { "version": <scene_versions row>, "charged": <credits debited by THIS call>, "balance": <after>, "replay": bool }
-- Raises:
--   'insufficient_credits: need <n>, have <b>'  (P0001) balance below the price, or negative
--   'rate_limited: max <n> per hour'            (P0001) too many versions in the last hour
--   'project not found' / 'parent not found'    (P0002)
--   'idempotency key reused ...'                (23505) same key, different project or plan
--   bad action / key / plan                     (22023)
create or replace function public.save_scene_version(
  p_user_id         uuid,
  p_project_id      uuid,
  p_parent_id       uuid,
  p_prompt          text,
  p_plan            jsonb,
  p_action          text,
  p_idempotency_key text
) returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_row     public.scene_versions;
  v_action  text := p_action;
  v_cost    integer;
  v_balance integer;
  v_recent  integer;
  v_index   integer;
begin
  if public.scene_action_cost(p_action) is null then
    raise exception 'unknown action %', p_action using errcode = '22023';
  end if;
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 128 then
    raise exception 'idempotency key required' using errcode = '22023';
  end if;
  if p_plan is null or jsonb_typeof(p_plan) <> 'object' then
    raise exception 'plan must be an object' using errcode = '22023';
  end if;
  if p_prompt is null or char_length(p_prompt) > 2000 then
    raise exception 'prompt too long' using errcode = '22023';
  end if;
  if not exists (select 1 from public.projects where id = p_project_id and user_id = p_user_id) then
    raise exception 'project not found' using errcode = 'P0002';
  end if;

  perform public.lock_user_credits(p_user_id);

  -- A replay returns the saved version before anything is counted or charged again.
  select * into v_row from public.scene_versions
   where user_id = p_user_id and idempotency_key = p_idempotency_key;
  if found then
    if v_row.project_id <> p_project_id or v_row.plan is distinct from p_plan then
      raise exception 'idempotency key reused with different details' using errcode = '23505';
    end if;
    return jsonb_build_object('version', to_jsonb(v_row), 'charged', 0,
                              'balance', public.user_balance(p_user_id), 'replay', true);
  end if;

  if p_parent_id is not null and not exists (
    select 1 from public.scene_versions where id = p_parent_id and project_id = p_project_id
  ) then
    raise exception 'parent not found' using errcode = 'P0002';
  end if;

  -- The action follows the project, not the browser: the first version is a generation.
  select coalesce(max(index) + 1, 0) into v_index from public.scene_versions where project_id = p_project_id;
  if v_index = 0 then
    v_action := 'generate';
  elsif v_action in ('edit', 'adjust') and p_parent_id is null then
    raise exception '% needs the version it changes', v_action using errcode = '22023';
  end if;
  v_cost := public.scene_action_cost(v_action);

  select count(*) into v_recent from public.scene_versions
   where user_id = p_user_id and created_at > now() - interval '1 hour';
  if v_recent >= public.scene_version_hourly_cap() then
    raise exception 'rate_limited: max % per hour', public.scene_version_hourly_cap() using errcode = 'P0001';
  end if;

  v_balance := public.user_balance(p_user_id);
  if v_balance < 0 or v_balance < v_cost then
    raise exception 'insufficient_credits: need %, have %', v_cost, v_balance using errcode = 'P0001';
  end if;

  insert into public.scene_versions (project_id, user_id, index, prompt, parent_id, plan, action, cost_credits, idempotency_key)
  values (p_project_id, p_user_id, v_index, p_prompt, p_parent_id, p_plan, v_action, v_cost, p_idempotency_key)
  returning * into v_row;

  if v_cost > 0 then
    insert into public.credit_ledger (user_id, amount, reason, ref, project_id)
    values (p_user_id, -v_cost, case v_action when 'generate' then 'scene_generation' else 'prompt_edit' end,
            'version:' || v_row.id::text, p_project_id);
  end if;

  return jsonb_build_object('version', to_jsonb(v_row), 'charged', v_cost,
                            'balance', v_balance - v_cost, 'replay', false);
end $$;

revoke all on function public.scene_action_cost(text) from public, anon;
revoke all on function public.scene_version_hourly_cap() from public, anon;
revoke all on function public.save_scene_version(uuid, uuid, uuid, text, jsonb, text, text) from public, anon, authenticated;
grant execute on function public.scene_action_cost(text) to authenticated, service_role;
grant execute on function public.scene_version_hourly_cap() to authenticated, service_role;
grant execute on function public.save_scene_version(uuid, uuid, uuid, text, jsonb, text, text) to service_role;
