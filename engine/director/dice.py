"""The creative dice (spec §3 stage 2, §6 layers 2-3). Pure and deterministic: the same seed, pins,
history, avoid list and viability always give the same direction. Order: viability first, then avoid on
the viable pool (relaxed only if it would empty it), then never-used directions (weighted random), then
used ones least-recently-used first. So a subject gets every eligible direction before any repeat, and a
non-viable direction never hides a viable one. Variety comes from here, not the LLM (§11).
Viability is tested LAZILY: every candidate is ranked by (avoid relax level, unseen before seen, then a
per-candidate seeded key or least-recent use) and viability is tested down that list, stopping at the
first viable one. That is the same rule as filtering the viable pool first (the first viable entry has
the least relax level any viable candidate has), at a few fallback builds instead of hundreds."""
import hashlib
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


def _avoid_level(c, avoid):
    """0: passes the whole avoid list. k: passes once the first k axes of AVOID_RELAX_ORDER are dropped
    (the same relaxation order the rule uses; an axis outside it is only ever relaxed last)."""
    last = len(AVOID_RELAX_ORDER) + 1
    return max((AVOID_RELAX_ORDER.index(a) + 1 if a in AVOID_RELAX_ORDER else last
                for a, vals in avoid.items() if c[a] in vals), default=0)


def _u(seed, cid):
    """A uniform (0, 1) draw per (seed, candidate): independent of list order and PYTHONHASHSEED."""
    h = int.from_bytes(hashlib.sha256(f"dice:{seed}:{cid}".encode()).digest()[:8], "big")
    return (h + 1) / (2 ** 64 + 2)


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


def ranked(seed, cands, *, pins=None, history=(), avoid=None, family_name=None, stats=None, dice=None):
    """[(relax level, candidate)] in the order the dice prefer them, viability aside: least-relaxed avoid
    level first; inside a level never-used directions (weighted random without replacement, one seeded
    key per candidate) before used ones (least recently used first)."""
    dice, pins = dice or DICE, pins or {}
    avoid = {a: set(v) for a, v in (avoid or {}).items() if a in AXES and a not in pins and v}
    history = list(history)
    last_use = {h: i for i, h in enumerate(history)}          # later index wins = most recent use
    recent_axes = _parsed(history[-dice["memoryN"]:])
    pw = pace_weights(family_name, stats, dice) if family_name else {}

    def key(c):
        cid = make_id(c)
        if cid in last_use:
            return (_avoid_level(c, avoid), 1, last_use[cid], "")
        return (_avoid_level(c, avoid), 0, -(_u(seed, cid) ** (1.0 / _weight(c, pw, recent_axes, dice))), cid)
    return [(k[0], c) for k, c in sorted(((key(c), c) for c in cands), key=lambda kc: kc[0])]


def roll(seed, values, *, pins=None, history=(), avoid=None, viable=None, family_name=None, stats=None, dice=None):
    """Viability first, then avoid (relaxed only if nothing viable passes it), then unseen before LRU.
    `tried` is how many viability checks the choice cost."""
    dice, pins = dice or DICE, pins or {}
    cands = candidates(values, pins, dice)
    if not cands:
        return Roll(None, ("no_candidates",))
    history = list(history)                              # read once: a generator must not be exhausted by set()
    seen = set(history)
    tried = 0
    for level, c in ranked(seed, cands, pins=pins, history=history, avoid=avoid, family_name=family_name,
                           stats=stats, dice=dice):
        tried += 1
        if viable is None or viable(c):
            flags = (("avoid_relaxed",) if level else ()) + (("repeat_after_rotation",) if make_id(c) in seen else ())
            return Roll(c, flags, tried)
    return Roll(None, ("nothing_viable",), tried)


def roll_duration(seed, dice=None):
    return random.Random(f"duration:{seed}").choice((dice or DICE)["durationsS"])
