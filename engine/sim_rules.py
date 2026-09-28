"""Sim checker rules (phase 6 Task 95; research/physics/BLOCKS.md §5). Pure; milliseconds. The checker runs
couple_sims before check_weather (a sim's coupled effects then get the weather/effect rules) and check_sims
right after it.

- sim_window: a window outside the clip is clamped and snapped to whole frames (sim_window_clamped); one over
  the block's bake.maxFrames (pre-roll included) is cut short at the end, never at the pre-roll
  (sim_window_truncated); a window under 2 frames is an error (sim_window_empty). bake_range() turns a checked
  window into the bake's frame range (engine/bake/window.py: GN sims bake on the render scene's own frames,
  every other format bakes from frame 1 and is offset at playback).
- sim_budget: at most one heavy sim per clip (Mantaflow gas and liquid bake for 10-90 min each).
- sim_duplicate: a sim id appears once (bakes and compile.json.sims are keyed by id).
- Time scale: a value outside the block's range is clamped by the script's param repair (param_clamped).
- sim_spawn_in_subject: a declared physics.spawnZone that meets the subject's bounds x 1.1 (the same margin
  as weather_rules.spawn_in_subject).
- sim_needs_world / sim_needs_profile: requiresWorld / requiresProfile / requiresSimFacts unmet is an error,
  never a silent drop; pipeline.py maps them to `unsupported` with the block's note (Task 120).
- sim_param_wind is raised by engine/script.py (a sim never owns wind).
- Couplings: a sim's physics.couplings adds its effects (to effects, block defaults) and light sims (to sims,
  with the parent's window) as coupled_added; a coupled child the subject cannot host is coupled_skipped.
  The catalog refuses a coupling to a heavy sim.
"""
import math

from engine.issues import Issue
from engine.weather_rules import SPAWN_MARGIN, _missing, _needs_world, _world

MIN_SIM_FRAMES = 2
_T_TOL = 1e-9


def _sims(s):
    v = s.get("sims")
    return v if isinstance(v, list) else []


def _manifest(catalog, ref):
    return catalog.get("sim", ref.get("id")) or {}


def _fps(s):
    return s["format"]["fps"]


def bake_range(s, ref, manifest):
    """The checked window of `ref` as a BakeFrames (bake_first, bake_last, clip_first, clip_last, preroll,
    offset): preroll = ceil(prerollS x fps), clip_last <= ceil(endS x fps) + 1."""
    from engine.bake.window import bake_frames_for
    b = manifest["bake"]
    return bake_frames_for(b["method"], ref["startS"], ref["endS"], _fps(s), b.get("prerollS", 0.0),
                           b.get("maxFrames", 10 ** 6))


def sim_window(s, catalog, issues):
    fps, dur = _fps(s), s["format"]["durationS"]
    for i, ref in enumerate(_sims(s)):
        m = _manifest(catalog, ref)
        a, b = ref["startS"], ref["endS"]
        a2 = round(max(0.0, min(a, dur)) * fps) / fps
        b2 = round(max(0.0, min(b, dur)) * fps) / fps
        if abs(a2 - a) > _T_TOL or abs(b2 - b) > _T_TOL:
            ref["startS"], ref["endS"] = a2, b2
            issues.append(Issue("sim_window_clamped", f"sims[{i}]",
                                f"{a}-{b} s -> {a2}-{b2} s (inside the clip, on whole frames)", "repaired"))
        if round(b2 * fps) - round(a2 * fps) < MIN_SIM_FRAMES:
            issues.append(Issue("sim_window_empty", f"sims[{i}]",
                                f"{ref['id']} runs {a}-{b} s: shorter than {MIN_SIM_FRAMES} frames in the clip", "error"))
            continue
        if (m.get("bake") or {}).get("method", "none") == "none":
            continue
        r = bake_range(s, ref, m)
        if r.truncated:
            ref["endS"] = (r.clip_last - 1) / fps
            issues.append(Issue("sim_window_truncated", f"sims[{i}].endS",
                                f"{ref['id']} bakes at most {m['bake']['maxFrames']} frames with its pre-roll: "
                                f"ends at {ref['endS']:.3f} s", "repaired"))


def sim_budget(s, catalog, issues):
    heavy, seen = [], set()
    for i, ref in enumerate(_sims(s)):
        if ref["id"] in seen:
            issues.append(Issue("sim_duplicate", f"sims[{i}]", f"{ref['id']} appears twice", "error"))
        seen.add(ref["id"])
        if (_manifest(catalog, ref).get("bake") or {}).get("costClass") == "heavy":
            heavy.append(ref["id"])
            if len(heavy) > 1:
                issues.append(Issue("sim_budget", f"sims[{i}]",
                                    f"one heavy sim per clip: {', '.join(heavy)}", "error"))


def sim_spawn_in_subject(s, catalog, profile, issues):
    """physics.spawnZone: 'above' spawns at heightFrac (or its heightParam's value) x the subject height above
    the ground; 'around' / 'behind' on a ring of radiusFrac x longest. Inside bounds x (1 + SPAWN_MARGIN) is an
    error."""
    h = profile.boundsMax[2] - profile.boundsMin[2]
    foot = math.hypot(profile.half[0], profile.half[1]) * (1.0 + SPAWN_MARGIN)
    for i, ref in enumerate(_sims(s)):
        z = (_manifest(catalog, ref).get("physics") or {}).get("spawnZone")
        if not z:
            continue
        if z["kind"] == "above":
            hp = z.get("heightParam")
            frac = (ref.get("params") or {}).get(hp, z["heightFrac"]) if hp else z["heightFrac"]
            if frac * h <= h * (1.0 + SPAWN_MARGIN):
                where = f"sims[{i}].params.{hp}" if hp else f"sims[{i}]"
                issues.append(Issue("sim_spawn_in_subject", where,
                                    f"{ref['id']} spawns at {frac:.2f} x the height, inside the subject "
                                    f"(needs > {1.0 + SPAWN_MARGIN:.2f})", "error"))
        elif z["radiusFrac"] * profile.longest <= foot:
            issues.append(Issue("sim_spawn_in_subject", f"sims[{i}]",
                                f"{ref['id']} spawns {z['radiusFrac'] * profile.longest:.3f} m out, inside the "
                                f"footprint ({foot:.3f} m)", "error"))


def _fact_missing(fact, profile, markers):
    from engine.physics import sim_facts
    if fact == "container":
        c = sim_facts.container(profile, markers)
        return not c or c["confidence"] != "high"
    if fact == "fillLine":
        return sim_facts.fill_line(profile, markers)["confidence"] != "high"
    if fact == "emitters":
        return not sim_facts.emitters(profile, markers)
    return True


def sim_needs(s, catalog, profile, issues):
    world = _world(s, catalog)
    markers = s.get("markers") or []
    for i, ref in enumerate(_sims(s)):
        m = _manifest(catalog, ref)
        ph = m.get("physics") or {}
        bad = _needs_world(ph.get("requiresWorld", {}), world)
        if bad:
            issues.append(Issue("sim_needs_world", f"sims[{i}]",
                                f"{ref['id']} needs {', '.join(bad)} (world {(s.get('world') or {}).get('id')})", "error"))
        miss = _missing(profile, m) + [f for f in ph.get("requiresSimFacts", []) if _fact_missing(f, profile, markers)]
        if miss:
            issues.append(Issue("sim_needs_profile", f"sims[{i}]", f"{ref['id']} needs {', '.join(miss)}", "error"))


def couple_sims(s, catalog, profile, issues):
    """A sim's couplings, one level (a coupled light sim's own couplings are expanded too; each id once)."""
    sims = _sims(s)
    if not sims:
        return
    effects = s.setdefault("effects", [])
    done, k = set(), 0
    while k < len(sims):
        ref = sims[k]
        k += 1
        if ref["id"] in done:
            continue
        done.add(ref["id"])
        for child in (_manifest(catalog, ref).get("physics") or {}).get("couplings", []):
            kind = "sim" if catalog.get("sim", child) else "effect"
            cm = catalog.get(kind, child) or {}
            target = sims if kind == "sim" else effects
            if any(isinstance(x, dict) and x.get("id") == child for x in target):
                continue
            if _missing(profile, cm):
                issues.append(Issue("coupled_skipped", f"sims[{k - 1}]",
                                    f"{child} (coupled:{ref['id']}) does not fit this subject", "info"))
                continue
            new = {"id": child, "params": {n: sp["default"] for n, sp in cm["params"].items()}}
            if kind == "sim":
                new.update(startS=ref["startS"], endS=ref["endS"])
            target.append(new)
            issues.append(Issue("coupled_added", f"{'sims' if kind == 'sim' else 'effects'}[{len(target) - 1}]",
                                f"{child} (coupled:{ref['id']})", "repaired"))


def check_sims(s, catalog, profile, issues):
    """Everything the checker runs on sims after check_weather."""
    if not _sims(s):
        return
    sim_window(s, catalog, issues)
    sim_budget(s, catalog, issues)
    sim_spawn_in_subject(s, catalog, profile, issues)
    sim_needs(s, catalog, profile, issues)
