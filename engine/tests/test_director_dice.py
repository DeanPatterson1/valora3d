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
