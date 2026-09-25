"""The safe fallback (spec §4.6): a pre-verified script for the job's direction, re-fitted to this
subject by construction and then checked. It generalises harness/suites/v0/t3_attempt.json (checked
on all nine eval subjects). If even this fails the checker the job raises FallbackError: a failing
script never renders."""
import copy
import math
import random

from engine import SCHEMA
from engine.checker import check
from engine.director.capabilities import assumption_lines, clip_line, play_clip_ref, wants_clip
from engine.director.details import middle_count, reverse_travel, vary_details, vary_lengths, vary_params
from engine.issues import errors
from engine.realism import realism_defaults

PACE_TARGET_S = {"calm": 2.5, "medium": 2.2, "hype": 1.6}   # middle-shot length target (eng)
HOOK_S, HERO_S, MIN_SEQ_S = 2.0, 3.0, 6.0                    # sequence: hookMaxS 2.5, lastShotMinS 1.5
SHORT_HERO_MIN_S, SHORT_DETAIL_MIN_S = 2.5, 1.0              # short (< MIN_SEQ_S) plan (eng): hero settle >= 1 s
GLOSSY = 0.2
ARC_DEG_PER_S = 20.0   # fallback arcs sweep <= 20 deg per second of shot (T3-14 caps the peak at 80 deg/s)
SLIDE_MIN_S = 2.5      # shorter macro shots push instead of slide: a short slide swings the azimuth past 80 deg/s
DARK_MOODS = ("premium_dark", "teal_night", "noir")
NOTE = "used the safe fallback script for this direction"
MAX_SHOTS_PER_10S = 7  # T3-01 upper bound (3-7 shots per 10 s)
MIN_MIDDLE_S = 1.0     # (eng) marker details never shorten middle shots below T3-02's 1.0 s median floor
DEFAULT_OPENER = "low_hero_push"
DETAIL_SCALES = (1.0, 0.5)   # (eng) layer-1 offset scales tried before the plain script (a lower tier retries)
_TIER_RANK = {"T1": 1, "T2": 2, "T3": 3}
FALLBACK_FLOOR_GLOSS, FALLBACK_HAZE = 0.4, 0.2   # phase-3 constants; layer 1 varies around them
DETAIL_CENTRES = {"world/studio_cyc": {"floorGloss": FALLBACK_FLOOR_GLOSS},
                  "effect/haze_volume": {"density": FALLBACK_HAZE}}
OPENER_HOOK = {  # hook cameras for non-default openers (values follow slot_camera's proven ranges) (eng)
    "arc_orbit": {"id": "arc_orbit", "params": {"startAzimuthDeg": 20.0, "sweepDeg": 25.0, "lensMm": 50.0,
                                                "elevationDeg": 6.0}},
}


class FallbackError(RuntimeError):
    pass


def _plan(duration, pace, template, seq, n_markers=0, count_seed=None, catalog=None):
    if not seq:
        return ["hook", "hero"], [duration * 0.4, duration * 0.6]
    if duration < MIN_SEQ_S:
        # Short plan (3-6 s): open on a detail, cut to the hero. Two shots keep 3-7 cuts per 10 s
        # (T3-01); detail + hero give two scales and a detail (T3-03) and a >= 1.5x scale cut (T3-04);
        # the hero is long enough for its settle to hold >= 1 s still (T3-13).
        hero = min(duration - SHORT_DETAIL_MIN_S, max(SHORT_HERO_MIN_S, duration * 0.6))
        return ["detail", "hero"], [duration - hero, hero]
    rem = duration - HOOK_S - HERO_S
    n = max(1, math.ceil(rem / PACE_TARGET_S[pace] - 1e-9))
    if count_seed is not None and not n_markers:   # layer 1: any shot count the pace's cadence allows
        n = middle_count(n, duration, rem, pace, count_seed, catalog, MAX_SHOTS_PER_10S, MIN_MIDDLE_S)
    middle = [slot["purpose"] for slot in template[1:-1]] or ["detail"]
    slots = [middle[i % len(middle)] for i in range(n)]
    # Every marker gets its own detail shot (spec §2b) while the plan stays inside T3-01 (<= 7 shots per
    # 10 s) and middle shots stay >= MIN_MIDDLE_S. Extra details are added before any slot is converted.
    n_max = min(math.floor(MAX_SHOTS_PER_10S * duration / 10.0 + 1e-9) - 2, math.floor(rem / MIN_MIDDLE_S + 1e-9))
    need = n_markers
    while slots.count("detail") < need and len(slots) < n_max:
        slots.append("detail")
    for i in range(len(slots) - 1, -1, -1):  # still short: turn later non-detail slots into details,
        if slots.count("detail") >= need or slots.count("motion") <= 1:  # keeping one motion shot
            break
        if slots[i] == "motion":
            slots[i] = "detail"
    if n_markers:  # without markers the template's own slot order stands
        slots = _alternate(slots)
    n = len(slots)
    return ["hook"] + slots + ["hero"], [HOOK_S] + [rem / n] * n + [HERO_S]


def _alternate(slots):
    """Spread the detail slots between the others (two macro shots back to back read as one)."""
    det = [s for s in slots if s == "detail"]
    rest = [s for s in slots if s != "detail"]
    out = []
    while det or rest:
        if det:
            out.append(det.pop())
        if rest:
            out.append(rest.pop(0))
    return out


def _times(lengths, fps, duration):
    bounds, t = [0], 0.0
    for length in lengths[:-1]:
        t += length
        bounds.append(round(t * fps) / fps)
    bounds.append(duration)
    return list(zip(bounds, bounds[1:]))


def slot_camera(purpose, k, fam, jitter=0.0, detail_jitter=0.0, opener=DEFAULT_OPENER):
    """Camera for a template slot. Values follow t3_attempt (known to pass the 30-degree rule and
    framing on every eval subject); vehicles get f/8 on full frames (T3-21 anti-miniature)."""
    if purpose == "detail":
        base = 20.0 if k % 2 == 0 else -25.0
        return {"id": "macro_detail", "params": {"move": "slide" if k % 2 == 0 else "push", "lensMm": 100.0,
                                                 "azimuthOffsetDeg": max(-60.0, min(60.0, base + detail_jitter))}}
    if purpose in ("hook", "establish") and opener in OPENER_HOOK:
        cam = copy.deepcopy(OPENER_HOOK[opener])
        cam["params"]["startAzimuthDeg"] += jitter
    elif purpose in ("hook", "establish"):
        cam = {"id": "low_hero_push", "params": {"azimuthDeg": 35.0 + jitter, "distance": 4.0, "lensMm": 40.0,
                                                 "heightFrac": 0.15, "pushFrac": 0.12, "easing": "in_out_cubic"}}
    elif purpose == "motion":
        cam = {"id": "arc_orbit", "params": {"startAzimuthDeg": -100.0 + jitter, "sweepDeg": 40.0, "lensMm": 70.0,
                                             "elevationDeg": 8.0}}
    else:  # hero / packshot
        cam = {"id": "arc_orbit", "params": {"startAzimuthDeg": 60.0 + jitter, "sweepDeg": -30.0, "lensMm": 55.0,
                                             "settleFrac": 0.4}}
    if fam == "vehicle":
        cam["params"]["fstop"] = 8.0
    return cam


def _world(direction, details=False):
    """With layer 1 on, floorGloss is left unset so vary_details seeds it around FALLBACK_FLOOR_GLOSS;
    without it (the phase-3 default) the constant stands."""
    w = getattr(direction, "world", "studio_cyc")
    if w == "studio_cyc":
        return {"id": w, "params": {"tone": direction.tone,
                                    **({} if details else {"floorGloss": FALLBACK_FLOOR_GLOSS})}}
    return {"id": w, "params": {}}


def _script(job, profile, pace, jitter, seq, catalog, skip=frozenset(), opener=DEFAULT_OPENER, details=True,
            scale=1.0):
    template = catalog.get("edit", "sequence")["templates"][job.family]
    purposes, lengths = _plan(job.fmt["durationS"], pace, template, seq, len(job.markers),
                              count_seed=job.seed if details and scale >= 1.0 else None, catalog=catalog)
    if details:  # layer 1: a count inside the pace's cadence (_plan), lengths inside the template windows
        lengths = vary_lengths(purposes, lengths, job.fmt["durationS"], job.seed, catalog, template, scale=scale)
    shots, d = [], 0
    for i, ((a, b), p) in enumerate(zip(_times(lengths, job.fmt["fps"], job.fmt["durationS"]), purposes)):
        sh = {"startS": a, "endS": b, "purpose": p, "focus": "subject", "transitionIn": "cut",
              "camera": slot_camera(p, d if p == "detail" else i, job.family, jitter, opener=opener)}
        prm = sh["camera"]["params"]
        settles = "settleFrac" in prm   # the slot asked for a settle (the hero), before layer 1 adds params
        if details:  # layer 1: the fallback's camera values are centres, not choices (then the caps below)
            path = f"shots[{i}].camera"
            if sh["camera"]["id"] == "arc_orbit" and p != "hook" and reverse_travel(job.seed, path):
                # Travel the other way. A motion arc covers the same angles in reverse; the hero keeps its
                # landing angle (its end frame is the pack shot) and arrives from the other side.
                shift = prm["sweepDeg"] if p == "motion" else 2.0 * prm["sweepDeg"]
                prm["startAzimuthDeg"] = round((prm["startAzimuthDeg"] + shift + 180.0) % 360.0 - 180.0, 4)
                prm["sweepDeg"] = -prm["sweepDeg"]
            if sh["camera"]["id"] == "macro_detail" and reverse_travel(job.seed, path):
                prm["azimuthOffsetDeg"] = -prm["azimuthOffsetDeg"]   # the detail seen from its other side
            vary_params(prm, "camera", sh["camera"]["id"], path, job.seed, catalog, keep=(), scale=scale,
                        family=job.family, mood=job.direction.mood, timed=True)
        if settles:  # a short hero settles longer so >= 1 s of it is still (T3-13)
            prm["settleFrac"] = round(min(0.5, max(prm["settleFrac"], 1.0 / (b - a))), 3)
        if sh["camera"]["id"] == "arc_orbit":  # the sweep happens in the moving (unsettled) part only
            cap = ARC_DEG_PER_S * (b - a) * (1.0 - prm.get("settleFrac", 0.0))
            prm["sweepDeg"] = round(max(-cap, min(cap, prm["sweepDeg"])), 1)
        if sh["camera"]["id"] == "macro_detail" and b - a < SLIDE_MIN_S:
            prm["move"] = "push"
        if p == "detail":
            if d < len(job.markers):
                sh["target"] = {"marker": job.markers[d]["id"]}
                if not job.markers[d]["anchor"].get("normal"):
                    # No surface normal: the slide's arc is aimed blind and can swing past T3-14's cap
                    # (measured 85 deg/s on cesium_man, 30 s, seed 4); a push keeps the azimuth fixed.
                    prm["move"] = "push"
            else:
                usable = [k for k in range(len(profile.detailPoints)) if k not in skip]
                if usable:
                    sh["target"] = {"detail": usable[(d - len(job.markers)) % len(usable)]}
            d += 1
        shots.append(sh)
    notes = list(job.notes) + assumption_lines(job.detected)
    if len(job.markers) > d:  # the T3-01 shot cap left no room for these markers
        notes.append(f"{len(job.markers) - d} marker(s) had no room for their own shot")
    s = {"schema": SCHEMA, "seed": job.seed, "direction": {"id": job.direction.id, "source": job.direction.source},
         "prompt": job.prompt, "format": dict(job.fmt), "assumptions": notes + [NOTE],
         "subject": {"placement": "ground", "motion": {"id": "static", "params": {}}, "finishOverrides": []},
         "world": _world(job.direction, details),
         "lighting": ({"id": "reflection_rig", "params": {}} if profile.glossShare >= GLOSSY
                      else {"id": "softbox_three_point",
                            "params": {} if details else {"rimStrength": 1.2, "fillRatio": 0.35}}),
         "effects": ([{"id": "haze_volume", "params": {} if details else {"density": FALLBACK_HAZE}}]
                     if job.direction.mood in DARK_MOODS else []),
         "grade": {"id": "mood_grade", "params": {"preset": job.direction.mood}},
         "shots": shots}
    if seq and job.fmt["durationS"] >= MIN_SEQ_S:
        s["edit"] = {"id": "sequence", "params": {"pace": pace}}
    if job.markers:
        s["markers"] = copy.deepcopy(job.markers)
    if job.detected:
        s["unsupported"] = copy.deepcopy(job.detected)
    if wants_clip(job.asks, catalog, profile):  # a supported movement ask is played, never dropped
        s["subject"]["motion"] = play_clip_ref(job.asks, profile)
        s["assumptions"].insert(-1, clip_line(profile, s["subject"]["motion"]["params"]["clip"]))
    realism = realism_defaults(profile, catalog)  # Task 12a
    if realism:
        s["realism"] = realism
    if details:  # layer 1 (Task 40a): seeded in-range look params the script left unset
        vary_details(s, job.seed, catalog, centres=DETAIL_CENTRES, scale=scale, family=job.family)
    return s


def _attempts(d, jitter):
    """(pace, jitter, seq, opener) tries. Pins win over the safety tweaks: a pinned opener or pace is kept
    through every try except the last resorts, and when both are pinned one is relaxed at a time (pace
    first, the less salient) before both are dropped. An unpinned interim direction (opener
    low_hero_push) reduces to phase 3's own four tries."""
    o, pinned = getattr(d, "opener", DEFAULT_OPENER), set(getattr(d, "pinned", ()))
    attempts = [(d.pace, jitter, True, o), (d.pace, 0.0, True, o)]
    if "opener" not in pinned:
        attempts.append((d.pace, 0.0, True, DEFAULT_OPENER))
    if "pace" not in pinned:
        attempts.append(("medium", 0.0, True, o if "opener" in pinned else DEFAULT_OPENER))
    if {"pace", "opener"} <= pinned:          # relax one pin at a time: keep the opener, then keep the pace
        attempts += [("medium", 0.0, True, o), (d.pace, 0.0, True, DEFAULT_OPENER)]
    if "opener" in pinned:                    # the unsequenced plan can still open on the pinned camera
        attempts.append(("medium", 0.0, False, o))
    attempts += [("medium", 0.0, True, DEFAULT_OPENER), ("medium", 0.0, False, DEFAULT_OPENER)]  # last resorts
    return list(dict.fromkeys(attempts))


def _pin_lines(s, d, catalog):
    """An assumption line for each pinned axis the passing script does not honour."""
    out = []
    pinned = set(getattr(d, "pinned", ()))
    if "opener" in pinned and s["shots"][0]["camera"]["id"] != d.opener:
        out.append(("opener", d.opener))
    if "pace" in pinned:
        from engine.director.floor import cadence_ok   # lazy: floor imports this module
        if not cadence_ok(s, d.pace, catalog):
            out.append(("pace", d.pace))
    return [f"your {axis} request ('{value}') did not pass the quality checks for this model, so it was adjusted"
            for axis, value in out]


def _first_passing(job, profile, catalog, pace, j, seq, skip, opener, details):
    """Layer 1 never costs a tier: the varied script is kept only when it passes the checker at the tier of
    the plain script (T3, or no worse than plain); else a smaller DETAIL_SCALES step, then plain."""
    from engine.director.floor import script_tier   # lazy: floor imports this module
    plain = None
    for scale in (DETAIL_SCALES if details else ()):
        s = _script(job, profile, pace, j, seq, catalog, skip, opener=opener, details=True, scale=scale)
        r = check(s, profile, catalog)
        if not r.ok:
            continue
        t = script_tier(r.script, profile, catalog)
        if t == "T3":
            return s, r
        if plain is None:
            ps = _script(job, profile, pace, j, seq, catalog, skip, opener=opener, details=False)
            plain = (ps, check(ps, profile, catalog))
        if not plain[1].ok or _TIER_RANK[t] >= _TIER_RANK[script_tier(plain[1].script, profile, catalog)]:
            return s, r
    if plain is None:
        ps = _script(job, profile, pace, j, seq, catalog, skip, opener=opener, details=False)
        plain = (ps, check(ps, profile, catalog))
    return plain


def build_fallback(job, profile, catalog, details=True):
    jitter = round(random.Random(f"fallback:{job.seed}").uniform(-10.0, 10.0), 1)
    last = None
    for pace, j, seq, opener in _attempts(job.direction, jitter):
        skip = set()   # detail points this subject cannot frame (e.g. the car's second glossy peak)
        while True:
            s, last = _first_passing(job, profile, catalog, pace, j, seq, frozenset(skip), opener, details)
            if last.ok:
                out = last.script
                lines = _pin_lines(out, job.direction, catalog) if getattr(job.direction, "pinned", ()) else []
                if lines:
                    notes = out["assumptions"]
                    at = notes.index(NOTE) if NOTE in notes else len(notes)
                    out["assumptions"] = notes[:at] + lines + notes[at:]
                return out
            bad = {s["shots"][int(i.path[6:i.path.index("]")])].get("target", {}).get("detail")
                   for i in errors(last.issues)
                   if i.code in ("framing_unfixable", "detail_target_off_centre") and i.path.startswith("shots[")}
            bad -= {None} | skip
            if not bad:
                break
            skip |= bad
    raise FallbackError("; ".join(f"{i.code} at {i.path}" for i in errors(last.issues)) or "fallback failed")
