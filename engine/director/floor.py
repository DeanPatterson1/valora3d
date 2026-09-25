"""The quality floor: novelty never buys a worse clip.
phase3_default(job): the interim direction's fallback without phase-4 details. The frozen-baseline test
(Task 41) proves it still reproduces phase 3 on the 90 frozen cases.
floor_tier(job) = min(T3, tier(phase3_default(job))), so the phase-3 default meets the floor by
definition and pipeline.direct can always deliver it (Task 46): below-floor delivery is impossible.
A direction is viable when its fallback passes the checker, keeps the opener, has a MEASURED cut cadence
inside its pace's shotsPer10s range, and reaches the floor. Viability uses a canonical seed and is cached
per (subject, format, markers, direction); the final gate re-checks the real seed."""
import dataclasses
import hashlib
import json
import math

from engine.craft_rules import score_script
from engine.director.axes import opener_of
from engine.director.baseline_phase3 import profile_key
from engine.director.direction import direction_of, interim_direction, make_id
from engine.director.fallback import MIN_SEQ_S, FallbackError, build_fallback

FLOOR_TIER = "T3"
_RANK = {"T1": 1, "T2": 2, "T3": 3}
CANONICAL_SEED = 0
_VIABLE = {}          # (subject, fmt, markers, direction id) -> bool; process-local, bounded below
_VIABLE_MAX = 20_000  # (eng)


def script_tier(script, profile, catalog):
    """Same definition as harness.director_eval.s_tier: script level only, not a quality grade."""
    items = score_script(script, profile, catalog)
    fail = lambda *pre: any(r.status == "fail" and r.id.startswith(pre) for r in items)  # noqa: E731
    if fail("T1-") or fail("T2-"):
        return "T1"
    return "T2" if fail("T3-", "V-") else "T3"


def cadence_range(pace, duration, catalog):
    lo, hi = catalog.get("edit", "sequence")["shotsPer10s"][pace]
    return math.floor(lo * duration / 10.0), math.ceil(hi * duration / 10.0)


def cadence_ok(script, pace, catalog):
    """The pace as CUT: shot count inside the pace's shotsPer10s range. Clips shorter than the sequence
    minimum (MIN_SEQ_S) use the 2-shot short plan and are exempt."""
    dur = script["format"]["durationS"]
    if dur < MIN_SEQ_S:
        return True
    lo, hi = cadence_range(pace, dur, catalog)
    return lo <= len(script["shots"]) <= hi


def phase3_default(job, profile, catalog):
    d = interim_direction(job.seed, profile, catalog)
    return build_fallback(dataclasses.replace(job, direction=d), profile, catalog, details=False)


def floor_tier(job, profile, catalog):
    try:
        base = script_tier(phase3_default(job, profile, catalog), profile, catalog)
    except FallbackError:
        base = "T1"
    return min((FLOOR_TIER, base), key=_RANK.get)


def _ctx_key(job, profile):
    mk = hashlib.sha256(json.dumps(job.markers, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return profile_key(profile), json.dumps(job.fmt, sort_keys=True), mk


def make_viable(job, profile, catalog):
    canon = dataclasses.replace(job, seed=CANONICAL_SEED)
    need = floor_tier(canon, profile, catalog)
    ctx = _ctx_key(job, profile)

    def viable(axes):
        key = ctx + (make_id(axes), need)
        if key not in _VIABLE:
            if len(_VIABLE) >= _VIABLE_MAX:
                _VIABLE.clear()
            try:
                s = build_fallback(dataclasses.replace(canon, direction=direction_of(axes, "dice")), profile, catalog)
                _VIABLE[key] = (opener_of(s) == axes["opener"] and cadence_ok(s, axes["pace"], catalog)
                                and _RANK[script_tier(s, profile, catalog)] >= _RANK[need])
            except FallbackError:
                _VIABLE[key] = False
        return _VIABLE[key]

    viable.floor = need
    return viable
