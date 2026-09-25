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


def _reference_choice_set(seed, values, history, avoid, viable):
    """The rule, brute force: viable pool -> least-relaxed avoid level with any viable member -> unseen
    before seen (seen: least recently used). Returns the set of ids the rule allows (unseen: any)."""
    from engine.director.dice import AVOID_RELAX_ORDER
    pool = [c for c in candidates(values) if viable(c)]
    if not pool:
        return set(), False

    def level(c):
        hit = [AVOID_RELAX_ORDER.index(a) + 1 for a, vals in avoid.items() if c[a] in vals]
        return max(hit, default=0)
    k = min(level(c) for c in pool)
    kept = [c for c in pool if level(c) <= k]
    unseen = [c for c in kept if make_id(c) not in history]
    if unseen:
        return {make_id(c) for c in unseen}, k > 0
    last = {h: i for i, h in enumerate(history)}
    return {make_id(min(kept, key=lambda c: last[make_id(c)]))}, k > 0


def test_lazy_roll_matches_the_eager_rule():
    import random as _r
    ids = [make_id(c) for c in candidates(V)]
    for trial in range(60):
        rng = _r.Random(trial)
        ok = set(rng.sample(ids, rng.randint(0, len(ids))))
        viable = lambda a, ok=ok: make_id(a) in ok        # noqa: E731
        hist = rng.sample(ids, rng.randint(0, len(ids)))
        avoid = {"mood": rng.sample(V["mood"], rng.randint(0, 2)), "opener": rng.sample(V["opener"], rng.randint(0, 1))}
        allowed, relaxed = _reference_choice_set(trial, V, hist, avoid, viable)
        r = roll(trial, V, history=hist, avoid=avoid, viable=viable)
        if not allowed:
            assert r.axes is None and "nothing_viable" in r.flags
            continue
        assert make_id(r.axes) in allowed and ("avoid_relaxed" in r.flags) == relaxed


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
