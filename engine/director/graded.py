"""Replay the owner-graded look for a graded world (engine/director/graded_recipes.json) on any subject.

Why (2026-09-29): customer renders, built by the fallback director's dice, did not look like the owner-graded
stills. For a world with a graded recipe the fallback now emits that recipe, not a dice-rolled variant of it:
  * world + params, lighting + params, effects, grade + params, edit pace: verbatim from the graded script;
  * shots: the graded shot list (hook low_hero_push 40 mm first, then the graded details / orbits, the graded hero
    last) with the graded camera params, timed proportionally to the requested duration; shots are dropped
    (later details first, then the orbit, then the first detail) when the duration cannot hold them, and
    repeated (details alternate their side) when it needs more cuts than the recipe has;
  * subject-dependent numbers stay the checker's: distances are in subject radii and the checker's own framing
    repair re-solves one that does not frame this subject; detail targets map onto the subject's own detail
    points; a hand-sized subject's macro distance is raised by small_macro_reach (the existing macro floor).
Seeds vary nothing here. A dice variant is what looked worse than the graded stills; the graded look is one look, and
the only seed-dependent choices left (the script's seed, foliage, rain and other simulated noise) are inside the
renderer. Everything is checked; None (the caller falls back to the dice path) when the recipe cannot be used:
a motion or clip ask, a pinned opener / pace the recipe does not honour, more markers than detail shots, a block
missing from the catalog's menu, or a check failure."""
import copy
import math
import statistics

from engine.checker import check
from engine.director import graded_recipes
from engine.director.capabilities import assumption_lines, wants_clip
from engine.issues import errors
from engine.realism import realism_defaults

HOOK_MAX_S, HOOK_MIN_S = 2.0, 1.0     # sequence: hookMaxS 2.5 (kept clear of it)
HERO_MIN_S, MID_MIN_S = 2.0, 1.0      # a hero settles >= 1 s still (T3-13); middle median floor (T3-02)
SHOT_MAX_S = 3.5                       # edit/sequence shotLenS upper bound
SLIDE_MIN_S = 1.4                      # graded slides ran 1.5 s (peak ~68 deg/s; the cap is 80)
MEDIAN_MAX_S = 2.9                     # medianLenS upper bound 3.0
MAX_PER_10S = 7                        # T3-01
GRADED_NOTE = "used the owner-graded {world} look"
_RECIPES = None


def recipes():
    global _RECIPES
    if _RECIPES is None:
        _RECIPES = graded_recipes.cached()
    return _RECIPES


def recipe_for(world_id):
    return recipes().get(world_id)


def _drop_order(shots):
    """Middle shot indices, first-to-drop first: repeated details, then non-details, then the first detail."""
    seen_detail = False
    key = []
    for i, sh in enumerate(shots[1:-1], 1):
        if sh["purpose"] == "detail":
            cls = 2 if not seen_detail else 0
            seen_detail = True
        else:
            cls = 1
        key.append(((cls, -i), i))
    return [i for _, i in sorted(key)]


def _fit(base, lo, hi, total):
    """Lengths proportional to base, clamped to [lo, hi] per shot, summing to total; None when infeasible."""
    if sum(lo) > total + 1e-9 or sum(hi) < total - 1e-9:
        return None
    n = len(base)
    scale = total / sum(base)
    x = [b * scale for b in base]
    for _ in range(50):
        x = [min(hi[i], max(lo[i], x[i])) for i in range(n)]
        diff = total - sum(x)
        if abs(diff) < 1e-9:
            return x
        free = [i for i in range(n) if (diff > 0 and x[i] < hi[i] - 1e-12) or (diff < 0 and x[i] > lo[i] + 1e-12)]
        if not free:
            return None
        w = sum(base[i] for i in free)
        for i in free:
            x[i] += diff * base[i] / w
    return None


def plan(recipe_shots, duration, cad):
    """[(recipe shot, length)] for this duration: the recipe's shots (hook first, hero last) within the cadence
    range cad = (lo, hi) shots, or None."""
    lo_n, hi_n = cad
    hi_n = min(hi_n, math.floor(MAX_PER_10S * duration / 10.0 + 1e-9))
    shots = [copy.deepcopy(s) for s in recipe_shots]
    order = _drop_order(shots)
    while len(shots) > max(hi_n, 2):                       # too many cuts for this length: drop
        if len(shots) - 2 <= 0:
            return None
        victim = shots[order[0]]
        shots = [s for s in shots if s is not victim]
        order = _drop_order(shots)
    mids = [s for s in shots[1:-1]]
    k = 0

    def repeat():
        nonlocal k
        src = copy.deepcopy(mids[k % len(mids)])
        prm = src["camera"]["params"]
        if "azimuthOffsetDeg" in prm and (k // len(mids) + 1) % 2:
            prm["azimuthOffsetDeg"] = -prm["azimuthOffsetDeg"]      # the repeat sees the detail from its other side
        shots.insert(len(shots) - 1, src)
        k += 1
    while len(shots) < lo_n and mids:                      # too few cuts: repeat the middle shots in order
        repeat()
    while True:
        n = len(shots)
        lo = [HOOK_MIN_S] + [MID_MIN_S] * (n - 2) + [HERO_MIN_S]
        hi = [HOOK_MAX_S] + [SHOT_MAX_S] * (n - 1)
        lens = _fit([s["lengthS"] for s in shots], lo, hi, duration)
        if lens is not None and statistics.median(lens) > MEDIAN_MAX_S and mids and n < max(hi_n, 2):
            repeat()                                       # the median shot is too long: one more cut
            continue
        if lens is not None and statistics.median(lens) <= MEDIAN_MAX_S:
            return list(zip(shots, lens))
        if lens is None and n > 2:
            order = _drop_order(shots)
            victim = shots[order[0]]
            shots = [s for s in shots if s is not victim]
            continue
        return None


def _with_atmosphere(effects, catalog):
    """T2-07 wants an atmosphere block outdoors, or the clip misses the T3 floor and the pipeline would swap it for
    the studio default. The graded courtyard had none (rain is not an atmosphere block), so it gets the haze the two
    other graded worlds used (their recipe's own haze_volume params: light, 0.2 density), in front of its effects."""
    if any((catalog.get("effect", e["id"]) or {}).get("atmosphere") for e in effects):
        return effects
    haze = next((e for r in recipes().values() for e in r["effects"] if e["id"] == "haze_volume"), None)
    return ([copy.deepcopy(haze)] if haze else []) + effects


def _timed(pairs, fps, duration):
    from engine.director.fallback import _times
    return _times([ln for _, ln in pairs], fps, duration)


def _usable(profile, skip):
    return [k for k in range(len(profile.detailPoints)) if k not in skip]


def graded_script(job, profile, catalog, skip=frozenset()):
    """The unchecked graded script for this job, or None when the recipe does not apply."""
    from engine.director.fallback import (DEFAULT_OPENER, MIN_SEQ_S, NOTE, _wind_blocked, asked_motion,
                                          small_macro_reach, subject_side, wind_hostable)
    from engine.director.fallback import SCHEMA
    from engine.director.axes import wind_speed
    from engine.director.floor import cadence_range
    d = job.direction
    wid = getattr(d, "world", None)
    r = graded_recipes.usable(wid, catalog)
    if r is None or any(getattr(d, a) != v for a, v in graded_recipes.direction_axes(r).items()):
        return None   # not this world's graded direction (a prompt pinned an axis, or a hand-built direction)
    if asked_motion(job, profile, catalog) is not None or wants_clip(job.asks, catalog, profile):
        return None
    pace = d.pace
    dur = job.fmt["durationS"]
    seq = dur >= MIN_SEQ_S
    cad = cadence_range(pace, dur, catalog) if seq else (2, 3)
    pairs = plan(r["shots"], dur, cad)
    if pairs is None:
        return None
    if len(job.markers) > sum(1 for sh, _ in pairs if sh["purpose"] == "detail"):
        return None
    shots, dn = [], 0
    usable = _usable(profile, skip)
    for (rs, _), (a, b) in zip(pairs, _timed(pairs, job.fmt["fps"], dur)):
        sh = {"startS": a, "endS": b, "purpose": rs["purpose"], "focus": rs.get("focus", "subject"),
              "camera": copy.deepcopy(rs["camera"])}
        prm = sh["camera"]["params"]
        if "settleFrac" in prm and rs["purpose"] == "hero" and prm["settleFrac"]:
            prm["settleFrac"] = round(min(0.5, max(prm["settleFrac"], 1.0 / (b - a))), 3)   # >= 1 s still (T3-13)
        if sh["camera"]["id"] == "arc_orbit" and b - a < rs["lengthS"]:
            prm["sweepDeg"] = round(prm["sweepDeg"] * (b - a) / rs["lengthS"], 1)   # a shorter shot keeps the graded rate
        if sh["camera"]["id"] == "macro_detail" and prm.get("move") == "slide" and b - a < SLIDE_MIN_S:
            prm["move"] = "push"   # (eng) the graded 1.5 s slide stands; a shorter one swings past T3-14 (85 deg/s at 1.2 s)
        if rs["purpose"] == "detail":
            if dn < len(job.markers):
                sh["target"] = {"marker": job.markers[dn]["id"]}
                if not job.markers[dn]["anchor"].get("normal"):
                    prm["move"] = "push"
            elif usable and "target" in rs:
                sh["target"] = {"detail": usable[rs["target"].get("detail", 0) % len(usable)]}
            dn += 1
        shots.append(sh)
    notes = list(job.notes) + assumption_lines(job.detected) + [GRADED_NOTE.format(world=wid)]
    s = {"schema": SCHEMA, "seed": job.seed, "direction": {"id": d.id, "source": d.source}, "prompt": job.prompt,
         "format": dict(job.fmt), "assumptions": notes + [NOTE],
         "subject": {"placement": "ground", "motion": {"id": "static", "params": {}}, "finishOverrides": []},
         "world": copy.deepcopy(r["world"]), "lighting": copy.deepcopy(r["lighting"]),
         "effects": _with_atmosphere(copy.deepcopy(r["effects"]), catalog), "grade": copy.deepcopy(r["grade"]), "shots": shots}
    if seq:
        s["edit"] = copy.deepcopy(r["edit"]) if r.get("edit") else {"id": "sequence", "params": {"pace": pace}}
    if job.markers:
        s["markers"] = copy.deepcopy(job.markers)
    if job.detected:
        s["unsupported"] = copy.deepcopy(job.detected)
    realism = realism_defaults(profile, catalog)
    if realism:
        s["realism"] = realism
    world = catalog.get("world", wid) or {}
    if not wind_hostable(world, catalog):
        _wind_blocked(s, job, profile, catalog)
    elif getattr(d, "wind", "calm") != "calm":
        s["wind"] = {"id": "wind", "params": {"speedMs": wind_speed(d.wind, world, job.seed)}}
    subject_side(s, profile, catalog)
    small_macro_reach(s, profile, catalog)
    return s


def build_graded(job, profile, catalog):
    """The checked graded script (the checker's repaired copy), or None (use the dice path)."""
    skip = set()
    while True:
        s = graded_script(job, profile, catalog, frozenset(skip))
        if s is None:
            return None
        r = check(s, profile, catalog)
        if r.ok:
            return r.script
        bad = {s["shots"][int(i.path[6:i.path.index("]")])].get("target", {}).get("detail")
               for i in errors(r.issues)
               if i.code in ("framing_unfixable", "detail_target_off_centre") and i.path.startswith("shots[")}
        bad -= {None} | skip
        if not bad:
            return None
        skip |= bad
