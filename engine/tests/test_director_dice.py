import os
import subprocess
import sys
from pathlib import Path

from engine.director.dice import candidates, roll, roll_duration
from engine.director.direction import make_id

V = {"world": ["studio_cyc"], "mood": ["clean", "premium_dark", "teal_night"], "tone": ["white", "grey", "black"],
     "pace": ["calm", "medium"], "opener": ["low_hero_push", "arc_orbit"], "weather": ["dry"], "wind": ["calm"]}


def test_candidates_respect_tone_compatibility_unless_tone_is_pinned():
    c = candidates(V)
    assert all(x["tone"] == "black" for x in c if x["mood"] in ("premium_dark", "teal_night"))
    assert any(x["tone"] == "white" for x in candidates(V, pins={"mood": "premium_dark", "tone": "white"}))


def test_same_inputs_same_direction_replayable():
    assert roll(7, V).axes == roll(7, V).axes
    assert len({make_id(roll(s, V).axes) for s in range(40)}) >= 8


def test_pins_are_never_overridden():
    for s in range(20):
        a = roll(s, V, pins={"mood": "noir", "pace": "calm"}).axes
        assert a["mood"] == "noir" and a["pace"] == "calm"


def test_whole_viable_pool_before_any_repeat():
    viable = lambda a: a["opener"] == "arc_orbit" and a["mood"] != "clean"   # noqa: E731
    pool = [c for c in candidates(V) if viable(c)]
    hist = []
    for s in range(len(pool)):
        r = roll(s, V, history=hist, viable=viable)
        assert make_id(r.axes) not in hist and "repeat_after_rotation" not in r.flags
        hist.append(make_id(r.axes))
    assert {make_id(c) for c in pool} == set(hist)
    r = roll(99, V, history=hist, viable=viable)                        # pool exhausted -> LRU repeat
    assert make_id(r.axes) == hist[0] and "repeat_after_rotation" in r.flags


def test_non_viable_never_chosen_even_when_unseen():
    for s in range(20):
        assert roll(s, V, viable=lambda a: a["opener"] == "arc_orbit").axes["opener"] == "arc_orbit"
    r = roll(3, V, viable=lambda a: False)
    assert r.axes is None and "nothing_viable" in r.flags


def test_avoid_applies_to_the_viable_pool_and_relaxes_only_when_it_is_empty():
    viable = lambda a: a["opener"] == "arc_orbit"              # noqa: E731
    for s in range(10):
        r = roll(s, V, avoid={"mood": ["clean", "premium_dark"]}, viable=viable)
        assert r.axes["mood"] == "teal_night" and r.axes["opener"] == "arc_orbit" and "avoid_relaxed" not in r.flags
    only_bad = lambda a: a["mood"] == "clean"                   # noqa: E731  the viable pool is all 'clean'
    r = roll(1, V, avoid={"mood": ["clean"]}, viable=only_bad)
    assert r.axes["mood"] == "clean" and "avoid_relaxed" in r.flags


def test_avoid_excludes_and_relaxes_instead_of_emptying():
    for s in range(20):
        assert roll(s, V, avoid={"mood": ["teal_night"]}).axes["mood"] != "teal_night"
    r = roll(1, V, avoid={"mood": ["clean", "premium_dark", "teal_night"]})
    assert r.axes is not None and "avoid_relaxed" in r.flags


def test_pins_beat_avoid():
    assert roll(1, V, pins={"mood": "clean"}, avoid={"mood": ["clean"]}).axes["mood"] == "clean"


def test_duration_is_seeded_and_in_range():
    assert roll_duration(5) == roll_duration(5) and {roll_duration(s) for s in range(40)} == {8, 10, 12}


_ROLL_SCRIPT = """
from engine.director.dice import roll
from engine.director.direction import make_id
V = %r
hist, out = [], []
for seed in range(6):
    r = roll(seed, V, history=list(hist), avoid={"mood": ["clean"], "opener": ["low_hero_push"]})
    hist.append(make_id(r.axes))
    out.append(make_id(r.axes) + "|" + ",".join(sorted(r.flags)))
print(";".join(out))
""" % (V,)


def test_roll_is_deterministic_across_processes_and_hash_seeds():
    """Set iteration order changes with PYTHONHASHSEED; a roll that leaked it would differ run to run."""
    root = Path(__file__).resolve().parents[2]

    def run(hash_seed):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(root)}
        return subprocess.run([sys.executable, "-c", _ROLL_SCRIPT], cwd=root, env=env, capture_output=True,
                              text=True, check=True, timeout=60).stdout.strip()

    a, b = run("0"), run("12345")
    assert a and a == b


def _reference_choice(seed, values, history, avoid, viable, family_name=None, stats=None):
    """The rule, eager and brute force, written independently of dice.py: filter the viable pool, keep
    the least-relaxed avoid level any viable member has, then among the never-used directions draw one
    by weighted sampling (Efraimidis-Spirakis: the largest u ** (1 / w), u a per-(seed, id) SHA-256
    draw, w = pace share + floor when the family's stats are trusted, x nearPenalty when within
    minDistance of one of the last memoryN used); none unseen -> the least recently used. Returns
    (exact id or None, relaxed)."""
    import hashlib
    import math

    from engine.director.axes import DICE
    from engine.director.dice import AVOID_RELAX_ORDER
    from engine.director.direction import AXES, parse_id
    from engine.director.taste import MIN_STAT_N
    pool = [c for c in candidates(values) if viable(c)]
    if not pool:
        return None, False

    def level(c):
        hit = [AVOID_RELAX_ORDER.index(a) + 1 for a, vals in avoid.items() if c[a] in vals]
        return max(hit, default=0)
    k = min(level(c) for c in pool)
    kept = [c for c in pool if level(c) <= k]
    unseen = [c for c in kept if make_id(c) not in history]
    if not unseen:
        last = {h: i for i, h in enumerate(history)}
        return make_id(min(kept, key=lambda c: last[make_id(c)])), k > 0
    aw = DICE["axisWeights"]
    recent = [parse_id(h) for h in history[-DICE["memoryN"]:]]
    energy = ((stats or {}).get("families", {}).get(family_name) or {}).get("energy") or {}
    trusted = family_name and energy.get("trusted") is True and energy.get("n", 0) >= MIN_STAT_N

    def weight(c):
        w = (energy["shares"].get(c["pace"], 0) + DICE["weightFloor"] if c["pace"] in energy["shares"]
             else DICE["weightFloor"]) if trusted else 1.0
        near = any(sum(aw[x] for x in AXES if c[x] != r[x]) / sum(aw.values()) < DICE["minDistance"] for r in recent)
        return w * (DICE["nearPenalty"] if near else 1.0)

    def draw(cid):
        h = int.from_bytes(hashlib.sha256(f"dice:{seed}:{cid}".encode()).digest()[:8], "big")
        return (h + 1) / (2 ** 64 + 2)
    best = max(unseen, key=lambda c: (math.log(draw(make_id(c))) / weight(c), [-ord(ch) for ch in make_id(c)]))
    return make_id(best), k > 0


STATS = {"families": {"fam": {"energy": {"trusted": True, "n": 10 ** 6, "shares": {"calm": 0.8, "medium": 0.2}}}}}


def test_lazy_roll_matches_the_eager_weighted_rule_exactly():
    import random as _r
    ids = [make_id(c) for c in candidates(V)]
    for trial in range(120):
        rng = _r.Random(trial)
        ok = set(rng.sample(ids, rng.randint(0, len(ids))))
        viable = lambda a, ok=ok: make_id(a) in ok        # noqa: E731
        hist = rng.sample(ids, rng.randint(0, len(ids)))
        avoid = {"mood": rng.sample(V["mood"], rng.randint(0, 2)), "opener": rng.sample(V["opener"], rng.randint(0, 1))}
        fam = ("fam", STATS) if trial % 2 else (None, None)
        want, relaxed = _reference_choice(trial, V, hist, avoid, viable, *fam)
        r = roll(trial, V, history=hist, avoid=avoid, viable=viable, family_name=fam[0], stats=fam[1])
        if want is None:
            assert r.axes is None and "nothing_viable" in r.flags
            continue
        assert make_id(r.axes) == want and ("avoid_relaxed" in r.flags) == relaxed


def test_the_eager_oracle_catches_a_wrong_weighting(monkeypatch):
    """Negative control: with the weights flattened, the exact comparison must fail for some trial."""
    import random as _r

    import engine.director.dice as dice
    monkeypatch.setattr(dice, "_weight", lambda *a: 1.0)
    ids, misses = [make_id(c) for c in candidates(V)], 0
    for trial in range(120):
        rng = _r.Random(trial)
        hist = rng.sample(ids, rng.randint(0, len(ids) // 2))
        want, _ = _reference_choice(trial, V, hist, {}, lambda a: True, "fam", STATS)
        misses += make_id(roll(trial, V, history=hist, family_name="fam", stats=STATS).axes) != want
    assert misses > 0


def test_a_generator_history_is_read_once_and_fully():
    viable = lambda a: a["opener"] == "arc_orbit"                  # noqa: E731
    pool = [make_id(c) for c in candidates(V) if viable(c)]
    for s in range(6):
        want = roll(s, V, history=list(pool), viable=viable)
        got = roll(s, V, history=(h for h in pool), viable=viable)
        assert got == want and "repeat_after_rotation" in got.flags
    part = pool[:-1]
    assert roll(2, V, history=iter(part), viable=viable) == roll(2, V, history=part, viable=viable)


def test_viability_is_tested_lazily_and_stops_at_the_first_viable():
    calls = []

    def viable(a):
        calls.append(make_id(a))
        return True
    r = roll(4, V, viable=viable)
    assert calls == [make_id(r.axes)] and r.tried == 1
    calls.clear()
    only = make_id(candidates(V)[-1])
    r = roll(4, V, viable=lambda a: calls.append(1) or make_id(a) == only)
    assert make_id(r.axes) == only and len(calls) == r.tried <= len(candidates(V))
