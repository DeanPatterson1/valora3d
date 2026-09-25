import pytest

from engine.catalog import Catalog
from engine.director.baseline_phase3 import profile_key
from engine.director.direction import make_id
from engine.director.job import make_job
from engine.director.variety import DirectionIncompatible, choose_direction, reachable, subject_key
from engine.tests.test_director_package import _p

FMT = {"aspect": "9:16", "durationS": 10, "fps": 30}


def _choose(prompt="", seed=1, model="pocket_watch", **kw):
    cat, p = Catalog.load(), _p(model)
    return choose_direction(prompt, p, cat, seed, FMT, job=make_job("a 10 second clip", p, cat, seed=seed), **kw)


def test_empty_prompt_rolls_dice_with_one_assumption_line():
    c = _choose()
    assert c.direction.source == "dice" and "dice" in c.notes[0] and len(c.notes) == 1


def test_prompt_pins_beat_the_dice_including_world_and_opener():
    for s in range(6):
        d = _choose("luxury, slow, studio, orbiting", seed=s).direction
        assert (d.mood, d.pace, d.world, d.opener) == ("premium_dark", "calm", "studio_cyc", "arc_orbit")
        assert d.pinned == ("mood", "opener", "pace", "world")


def test_pins_survive_the_interim_fallback(monkeypatch):
    import engine.director.variety as v
    monkeypatch.setattr(v, "make_viable", lambda *a, **k: (lambda axes: False))
    d = _choose("neon, slow", seed=3).direction
    assert d.source == "interim" and (d.mood, d.pace) == ("teal_night", "calm") and "mood" in d.pinned


def test_more_like_this_keeps_the_direction_and_pins_still_win():
    first = _choose(seed=1).direction
    assert _choose(seed=99, like=first).direction.axes() == first.axes()
    d = _choose("neon", seed=5, like={"direction": {"id": first.id}}).direction
    assert d.mood == "teal_night" and d.opener == first.opener and d.source == "more_like_this"


@pytest.mark.parametrize("like", ["nonsense", "studio_cyc/<b>/black/calm/arc_orbit/dry/calm",
                                  "moon_world/clean/white/calm/arc_orbit/dry/calm", {"direction": {}}, 42])
def test_like_unknown_or_foreign_values_is_an_explicit_error(like):
    with pytest.raises(DirectionIncompatible) as e:
        _choose(like=like)
    assert "can't be used for this model" in str(e.value)


def test_like_below_the_floor_is_an_explicit_error(monkeypatch):
    import engine.director.variety as v
    first = _choose(seed=1).direction
    monkeypatch.setattr(v, "make_viable", lambda *a, **k: (lambda axes: False))
    with pytest.raises(DirectionIncompatible, match="quality"):
        _choose(like=first)


@pytest.mark.parametrize("avoid", [{"mood": ["purple_rain"]}, {"colour": ["red"]}, {"mood": "clean"}])
def test_avoid_with_unknown_values_is_an_explicit_error(avoid):
    with pytest.raises(DirectionIncompatible):
        _choose(avoid=avoid)


def test_avoid_is_honoured():
    for s in range(6):
        assert _choose(seed=s, avoid={"mood": ["clean", "vivid"]}).direction.mood not in ("clean", "vivid")


def test_history_is_rotated():
    hist = [_choose(seed=s).direction.id for s in range(3)]
    for s in range(10, 14):
        assert _choose(seed=s, history=hist).direction.id not in hist


def test_subject_key_matches_the_frozen_baseline_key():
    p = _p("pocket_watch")
    assert subject_key(p) == profile_key(p) and subject_key(p) != subject_key(_p("sneaker"))


def test_reachable_uses_pins_format_and_viability():
    cat, p = Catalog.load(), _p("pocket_watch")
    job = make_job("a 10 second clip", p, cat, seed=0)
    free, pinned = reachable(p, cat, FMT, job=job), reachable(p, cat, FMT, job=job, prompt="luxury, slow")
    assert pinned["combinations"] < free["combinations"] and "viable" in free and free["viable"] <= free["combinations"]
    assert "world" in free["singleValued"] and "note" in free
    assert make_id(_choose().direction.axes()) == _choose().direction.id


def test_make_job_uses_the_dice_and_rolls_duration():
    cat, p = Catalog.load(), _p("pocket_watch")
    jobs = [make_job("", p, cat, seed=s) for s in range(12)]
    assert all(j.direction.source == "dice" for j in jobs)
    assert {j.fmt["durationS"] for j in jobs} <= {8, 10, 12} and len({j.fmt["durationS"] for j in jobs}) > 1
    assert any("dice direction" in n for n in jobs[0].notes)


def test_duration_order_pin_explicit_liked_rolled():
    cat, p = Catalog.load(), _p("pocket_watch")
    liked = {"direction": {"id": make_job("", p, cat, seed=1).direction.id}, "format": {"durationS": 12}}
    assert make_job("a 15 second clip", p, cat, seed=1, duration=8, like=liked).fmt["durationS"] == 15
    assert make_job("", p, cat, seed=1, duration=8, like=liked).fmt["durationS"] == 8
    assert make_job("", p, cat, seed=5, like=liked).fmt["durationS"] == 12


def test_given_direction_is_used_verbatim():
    cat, p = Catalog.load(), _p("pocket_watch")
    d = make_job("", p, cat, seed=1).direction
    assert make_job("", p, cat, seed=77, direction=d, duration=10).direction == d


def test_incompatible_like_is_director_input_error():
    from engine.director.job import DirectorInputError
    cat, p = Catalog.load(), _p("pocket_watch")
    with pytest.raises(DirectorInputError):
        make_job("", p, cat, seed=1, like="moon/clean/white/calm/arc_orbit/dry/calm")
    with pytest.raises(DirectorInputError):
        make_job("", p, cat, seed=1, like={"direction": {"id": make_job("", p, cat, seed=1).direction.id},
                                           "format": {"durationS": "forever"}})


def test_direct_forwards_duration():
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    r = direct("", _p("pocket_watch"), provider=FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3),
               seed=3, duration=10)
    assert r.script["format"]["durationS"] == 10
