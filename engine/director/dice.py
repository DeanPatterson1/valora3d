"""The creative dice (spec §3 stage 2, §6 layers 2-3). Pure and deterministic: the same seed, pins,
history, avoid list and viability always give the same direction. Order: viability first, then avoid on
the viable pool (relaxed only if it would empty it), then never-used directions (weighted random), then
used ones least-recently-used first. So a subject gets every eligible direction before any repeat, and a
non-viable direction never hides a viable one. Variety comes from here, not the LLM (§11)."""
import itertools
import random
from dataclasses import dataclass

from engine.director.axes import DICE, compatible
from engine.director.direction import AXES, make_id, parse_id
from engine.director.distance import direction_distance
from engine.director.taste import MIN_STAT_N

AVOID_RELAX_ORDER = ("wind", "weather", "pace", "tone", "opener", "world", "mood")  # least salient first


@dataclass(frozen=True)
class Roll:
    axes: dict | None
    flags: tuple = ()
    tried: int = 0


def candidates(values, pins=None, dice=None):
    pins = pins or {}
    pools = [[pins[a]] if a in pins else values[a] for a in AXES]
    out = []
    for combo in itertools.product(*pools):
        axes = dict(zip(AXES, combo))
        if "tone" in pins or compatible(axes, dice):
            out.append(axes)
    return out


def _apply_avoid(cands, avoid, pins):
    avoid = {a: set(v) for a, v in (avoid or {}).items() if a in AXES and a not in pins and v}
    relaxed = False
    for drop in (None,) + AVOID_RELAX_ORDER:
        if drop is not None and drop in avoid:
            avoid.pop(drop)
            relaxed = True
        kept = [c for c in cands if not any(c[a] in vals for a, vals in avoid.items())]
        if kept:
            return kept, relaxed
    return cands, True


def pace_weights(fam, stats, dice=None):
    """Corpus energy shares for this family when trusted (n >= MIN_STAT_N), plus a floor so a
    rare-but-good pace stays rollable (spec §9a use 3). Untrusted: {} (uniform)."""
    s = ((stats or {}).get("families", {}).get(fam) or {}).get("energy") or {}
    if s.get("trusted") is True and s.get("n", 0) >= MIN_STAT_N:
        return {k: v + (dice or DICE)["weightFloor"] for k, v in s["shares"].items()}
    return {}


def _weight(axes, pw, recent_axes, dice):
    w = pw.get(axes["pace"], dice["weightFloor"]) if pw else 1.0
    if any(direction_distance(axes, r, dice) < dice["minDistance"] for r in recent_axes):
        w *= dice["nearPenalty"]
    return w


def _parsed(ids):
    out = []
    for i in ids:
        try:
            out.append(parse_id(i))
        except ValueError:
            continue
    return out


def roll(seed, values, *, pins=None, history=(), avoid=None, viable=None, family_name=None, stats=None, dice=None):
    dice, pins, flags = dice or DICE, pins or {}, []
    cands = candidates(values, pins, dice)
    if not cands:
        return Roll(None, ("no_candidates",))
    pool = [c for c in cands if viable is None or viable(c)]          # 1. viability first
    if not pool:
        return Roll(None, ("nothing_viable",), len(cands))
    cands, relaxed = _apply_avoid(pool, avoid, pins)                  # 2. avoid on the viable pool
    if relaxed:
        flags.append("avoid_relaxed")
    history = list(history)                                           # 3. unseen first, then LRU
    last_use = {h: i for i, h in enumerate(history)}          # later index wins = most recent use
    unseen = [c for c in cands if make_id(c) not in last_use]
    seen = sorted((c for c in cands if make_id(c) in last_use), key=lambda c: last_use[make_id(c)])
    recent_axes = _parsed(history[-dice["memoryN"]:])
    pw = pace_weights(family_name, stats, dice) if family_name else {}
    rng = random.Random(f"dice:{seed}")
    keys = [rng.random() ** (1.0 / _weight(c, pw, recent_axes, dice)) for c in unseen]  # weighted, no replacement
    order = [c for _, c in sorted(zip(keys, unseen), key=lambda kc: (-kc[0], make_id(kc[1])))] + seen
    c = order[0]
    if make_id(c) in last_use:
        flags.append("repeat_after_rotation")
    return Roll(c, tuple(flags), len(pool))


def roll_duration(seed, dice=None):
    return random.Random(f"duration:{seed}").choice((dice or DICE)["durationsS"])
