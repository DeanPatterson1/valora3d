"""Weather, coupling and effect-world rules (research/physics/BLOCKS.md §3, §5). Pure; milliseconds; the
checker runs them after resolve_wind and before resolve_realism, so realism sees the final effect list
(e.g. wet_surface).

- Couplings (physics.couplings): a coupled child the author omitted is re-added right after its parent,
  in the parent's declared order, with block defaults (coupled_added, repaired). An LLM reply cannot write
  anything but {id, params}, so an omitted child is always this repair. Only an explicit
  {"id": child, "remove": true} entry while its parent is present is coupling_removed (error). A coupled
  child whose own requiresProfile the subject lacks is skipped (coupled_skipped, info): coupling never
  fails a clip.
- A requested effect whose requiresWorld the world fails (effect_needs_world), whose requiresProfile the
  subject lacks (effect_needs_profile), that shares a clip with an effect it excludes (exclusive_effects)
  or appears more than maxPerClip times (effect_max_per_clip) is an error; it is never silently dropped
  (the pipeline moves such asks to `unsupported` with the block's note, PHASING §3.6, Task 85).
- Ambient weather runs at real time (time_scale_weather, METHODS R4); fog in strong wind is a warning.
- spawn_in_subject / effect_off_screen / surface_state_continuity are the script-level guards.
  effect_off_screen does frustum maths for lens_drops only (it must land in a shot, Task 68); the other
  effects are left to PH-07 in the harness."""
from engine.issues import Issue

WEATHER_IDS = ("rain", "snow", "ground_fog", "wet_surface")   # ambient: time scale must stay 1.0 (METHODS R4)
FOG_WIND_MAX = 6.0      # (eng) m/s above which fog does not hold (BLOCKS §5)
SNOW_WIND_MAX = 11.0    # (eng) m/s above which snow reads as noise (Task 67; = engine/physics/snow.BLIZZARD_MS)
SPAWN_MARGIN = 0.10     # share of the footprint added around the subject (= checker.BOX_MARGIN)
_SPAWN_SUFFIXES = ("Position", "Lane")


def _world(s, catalog):
    return catalog.get("world", (s.get("world") or {}).get("id")) or {}


def _needs_world(req, world):
    """The requiresWorld keys this world fails (empty = it can host the block)."""
    bad = []
    for k in ("outdoor", "hasGround", "hasFoliage"):
        if k in req and bool(world.get(k, False)) != req[k]:
            bad.append(k)
    if "groundType" in req and world.get("groundType", "studio") not in req["groundType"]:
        bad.append("groundType")
    if "temperature" in req and world.get("temperature", "mild") not in req["temperature"]:
        bad.append("temperature")
    return bad


def _needs(m):
    need = m.get("requiresProfile") or []
    return [need] if isinstance(need, str) else list(need)


def _missing(profile, m):
    from engine.catalog import _has
    return [f for f in _needs(m) if not _has(profile, f)]


def _couple(effects, catalog, profile, removed, issues):
    """Couplings to closure (review chunk1 #8): an added child is itself a parent (A -> B -> C adds C in the
    same pass, so a second check changes nothing); each id is expanded once, so a cycle ends."""
    done = set()
    while True:
        parent = next((e["id"] for e in effects if e["id"] not in done), None)
        if parent is None:
            return
        done.add(parent)
        m = catalog.get("effect", parent) or {}
        cursor = [e["id"] for e in effects].index(parent)
        for child in (m.get("physics") or {}).get("couplings", []):
            if child in removed:
                issues.append(Issue("coupling_removed", f"effects[{cursor}]", f"{child} is coupled to {parent}", "error"))
                continue
            ids = [e["id"] for e in effects]
            if child in ids:
                cursor = max(cursor, ids.index(child))
                continue
            cm = catalog.get("effect", child) or {}
            if _missing(profile, cm):                     # a coupled child never fails the clip
                issues.append(Issue("coupled_skipped", f"effects[{cursor}]",
                                    f"{child} (coupled:{parent}) does not fit this subject", "info"))
                continue
            cursor += 1
            effects.insert(cursor, {"id": child, "params": {k: sp["default"] for k, sp in cm["params"].items()}})
            issues.append(Issue("coupled_added", f"effects[{cursor}]", f"{child} (coupled:{parent})", "repaired"))


def apply_weather_rules(s, catalog, profile, issues):
    effects = s.get("effects")
    if not isinstance(effects, list) or not effects:
        wind_rules(s, issues)
        return
    world = _world(s, catalog)
    removed = {e["id"] for e in effects if isinstance(e, dict) and e.get("remove")}
    if removed:
        effects[:] = [e for e in effects if not e.get("remove")]
    _couple(effects, catalog, profile, removed, issues)
    present = [e["id"] for e in effects]
    counts = {}
    for i, e in enumerate(effects):
        m = catalog.get("effect", e["id"]) or {}
        ph = m.get("physics") or {}
        counts[e["id"]] = counts.get(e["id"], 0) + 1
        if m.get("maxPerClip") is not None and counts[e["id"]] > m["maxPerClip"]:
            issues.append(Issue("effect_max_per_clip", f"effects[{i}]", f"{e['id']} more than {m['maxPerClip']}x", "error"))
        bad = _needs_world(ph.get("requiresWorld", {}), world)
        if bad:
            issues.append(Issue("effect_needs_world", f"effects[{i}]",
                                f"{e['id']} needs {', '.join(bad)} (world {s['world']['id']})", "error"))
        for x in ph.get("excludes", []):
            if x in present:
                issues.append(Issue("exclusive_effects", f"effects[{i}]", f"{e['id']} cannot share a clip with {x}", "error"))
        tsp = ph.get("timeScaleParam") or "timeScale"
        ts = (e.get("params") or {}).get(tsp, 1.0)
        if e["id"] in WEATHER_IDS and isinstance(ts, (int, float)) and float(ts) != 1.0:
            issues.append(Issue("time_scale_weather", f"effects[{i}]", "ambient weather runs at real time", "error"))
        miss = _missing(profile, m)
        if miss:
            issues.append(Issue("effect_needs_profile", f"effects[{i}]", f"{e['id']} needs {', '.join(miss)}", "error"))
    wind_rules(s, issues)


def wind_rules(s, issues):
    """Wind plausibility (warnings; BLOCKS §5)."""
    present = {e.get("id") for e in (s.get("effects") or []) if isinstance(e, dict)}
    speed = ((s.get("wind") or {}).get("params") or {}).get("speedMs", 0.0)
    if "ground_fog" in present and isinstance(speed, (int, float)) and speed > FOG_WIND_MAX:
        issues.append(Issue("wind_implausible", "wind", f"fog does not hold in {speed} m/s wind", "warning"))
    if "snow" in present and isinstance(speed, (int, float)) and speed > SNOW_WIND_MAX:
        issues.append(Issue("wind_implausible", "wind", f"a blizzard at {speed} m/s reads as noise", "warning"))


def spawn_in_subject(s, profile, catalog, issues):
    """An effect param named *Position or *Lane is a horizontal distance (metres) from the subject's centre
    where the effect spawns; inside the footprint + SPAWN_MARGIN it would spawn inside the subject."""
    half = max(profile.half[0], profile.half[1]) * (1.0 + 2.0 * SPAWN_MARGIN)
    for i, e in enumerate(s.get("effects") or []):
        m = catalog.get("effect", e.get("id")) or {}
        for k, v in (e.get("params") or {}).items():
            if k.endswith(_SPAWN_SUFFIXES) and (m.get("params", {}).get(k) or {}).get("type", "number") == "number" \
                    and isinstance(v, (int, float)) and abs(v) < half:
                issues.append(Issue("spawn_in_subject", f"effects[{i}].params.{k}",
                                    f"{v} m is inside the subject (footprint {half:.3f} m)", "error"))


def effect_off_screen(s, issues):
    """lens_drops names the shot it lands in; that shot must exist."""
    n = len(s.get("shots") or [])
    for i, e in enumerate(s.get("effects") or []):
        if e.get("id") == "lens_drops":
            shot = (e.get("params") or {}).get("shot", 0)
            if not isinstance(shot, (int, float)) or not 0 <= int(round(shot)) < n:
                issues.append(Issue("effect_off_screen", f"effects[{i}].params.shot",
                                    f"shot {shot} is not one of the clip's {n} shots", "error"))


def surface_state_continuity(s, issues):
    """The ground's wet/dry state is one per clip until a transition block exists (engine/script.py
    rejects shots[].surfaceState); this guards the future key."""
    clip = s.get("surfaceState")
    for i, sh in enumerate(s.get("shots") or []):
        if isinstance(sh, dict) and "surfaceState" in sh and sh["surfaceState"] != clip:
            issues.append(Issue("surface_state_continuity", f"shots[{i}].surfaceState",
                                f"{sh['surfaceState']!r} differs from the clip's {clip!r}", "error"))


def check_weather(s, catalog, profile, issues):
    """Everything the checker runs between resolve_wind and resolve_realism."""
    apply_weather_rules(s, catalog, profile, issues)
    spawn_in_subject(s, profile, catalog, issues)
    effect_off_screen(s, issues)
    surface_state_continuity(s, issues)
