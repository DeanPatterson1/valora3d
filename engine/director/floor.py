"""The quality floor: novelty never buys a worse clip.
phase3_default(job): the interim direction's fallback without phase-4 details. The frozen-baseline test
(Task 41) proves it still reproduces phase 3 on the 90 frozen cases.
floor_tier(job) = min(T3, tier(phase3_default(job))), so the phase-3 default meets the floor by
definition and pipeline.direct can always deliver it (Task 46): below-floor delivery is impossible.
A direction is viable when its fallback passes the checker, keeps the opener, has a MEASURED cut cadence
inside its pace's shotsPer10s range, and reaches the floor. Viability uses a canonical seed and is cached
per (catalog, subject, format, markers, asks, direction); the final gate re-checks the real seed.
floor_default(job) is the DELIVERY fallback when a script misses the floor: the interim direction with
the job's pins kept, dropping a pin (least salient first) only when the script with it fails the checker
or the floor, each drop recorded as an assumption line. Measurement (floor_tier) always uses the pure
phase3_default, and the pure default is the last resort, so delivery still always meets the floor."""
import dataclasses
import hashlib
import json
import math
import weakref

from engine.craft_rules import score_script
from engine.director.axes import opener_of
from engine.director.baseline_phase3 import profile_key
from engine.director.direction import direction_of, interim_direction, make_id, parse_id
from engine.director.fallback import MIN_SEQ_S, NOTE, FallbackError, build_fallback

FLOOR_TIER = "T3"
_RANK = {"T1": 1, "T2": 2, "T3": 3}
CANONICAL_SEED = 0
_VIABLE = {}          # (subject, fmt, markers, direction id) -> bool; process-local, bounded below
_VIABLE_MAX = 20_000  # (eng)
_CATALOG_FP = weakref.WeakKeyDictionary()
PIN_DROP_ORDER = ("wind", "weather", "pace", "tone", "opener", "world", "mood")  # least salient first


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


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def catalog_fingerprint(catalog):
    """Content hash of every block manifest: a changed catalog never reuses a cached verdict."""
    try:
        return _CATALOG_FP[catalog]
    except (KeyError, TypeError):
        pass
    blocks = getattr(catalog, "_blocks", None)
    fp = _h(sorted(([list(k), m] for k, m in blocks.items()), key=lambda km: km[0])) if blocks else str(id(catalog))
    try:
        _CATALOG_FP[catalog] = fp
    except TypeError:
        pass
    return fp


def _ctx_key(job, profile, catalog):
    """Everything besides the direction that changes the fallback: catalog, subject, format, markers and
    the requests (a motion ask plays a clip)."""
    return (catalog_fingerprint(catalog), profile_key(profile), json.dumps(job.fmt, sort_keys=True),
            _h(job.markers), _h([job.asks, job.detected]))


def make_viable(job, profile, catalog):
    canon = dataclasses.replace(job, seed=CANONICAL_SEED)
    need = floor_tier(canon, profile, catalog)
    ctx = _ctx_key(job, profile, catalog)

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


def floor_default(job, profile, catalog, need=None):
    """(script, dropped_axes): the delivery fallback that keeps the job's pins. Meets `need` (default
    floor_tier(job)) always: the pure phase3_default is the last resort and meets it by definition."""
    need = need or floor_tier(job, profile, catalog)
    d = job.direction
    base = parse_id(interim_direction(job.seed, profile, catalog).id)
    axes = d.axes() if hasattr(d, "axes") else {}
    keep = [a for a in getattr(d, "pinned", ()) if a in axes and axes[a] != base.get(a)]
    keep.sort(key=lambda a: -PIN_DROP_ORDER.index(a) if a in PIN_DROP_ORDER else -99)   # most salient first
    dropped = []
    while keep:
        pd = direction_of({**base, **{a: axes[a] for a in keep}}, "interim", pinned=keep)
        try:
            s = build_fallback(dataclasses.replace(job, direction=pd), profile, catalog, details=False)
            if _RANK[script_tier(s, profile, catalog)] >= _RANK[need]:
                return _with_drop_lines(s, dropped, axes), dropped
        except FallbackError:
            pass
        dropped.append(keep.pop())                       # least salient still kept
    return _with_drop_lines(phase3_default(job, profile, catalog), dropped, axes), dropped


def _with_drop_lines(s, dropped, axes):
    if dropped:
        lines = [f"your {a} request ('{axes[a]}') could not be kept at full quality for this model, so it was "
                 "changed" for a in dropped]
        notes = list(s.get("assumptions", []))
        at = notes.index(NOTE) if NOTE in notes else len(notes)
        s["assumptions"] = notes[:at] + lines + notes[at:]
    return s
