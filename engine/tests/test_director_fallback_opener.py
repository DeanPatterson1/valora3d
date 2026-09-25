import dataclasses

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.director.axes import opener_of
from engine.director.direction import direction_of
from engine.director.fallback import build_fallback
from engine.director.job import make_job
from engine.tests.test_director_package import _p

NINE = ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
        "sports_car", "toycar", "vintage_microscope"]
AX = {"world": "studio_cyc", "mood": "clean", "tone": "white", "pace": "medium", "opener": "low_hero_push",
      "weather": "dry", "wind": "calm"}


def _job(p, cat, seed, opener):
    return dataclasses.replace(make_job("a 10 second clip", p, cat, seed=seed),
                               direction=direction_of({**AX, "opener": opener}, "dice"))


@pytest.mark.parametrize("opener", ["low_hero_push", "arc_orbit"])
def test_fallback_uses_the_opener_on_the_watch(opener):
    cat, p = Catalog.load(), _p("pocket_watch")
    s = build_fallback(_job(p, cat, 3, opener), p, cat)
    assert check(s, p, cat).ok and opener_of(s) == opener


@pytest.mark.parametrize("model", NINE)
def test_every_subject_still_gets_a_valid_fallback_for_every_opener(model):
    """The fallback may swap to the safe opener, but it must never fail (spec §4.6)."""
    cat, p = Catalog.load(), _p(model)
    for opener in ("low_hero_push", "arc_orbit"):
        assert check(build_fallback(_job(p, cat, 4, opener), p, cat), p, cat).ok


def test_pinned_opener_is_kept_and_a_rejected_pin_is_recorded(monkeypatch):
    cat, p = Catalog.load(), _p("pocket_watch")
    job = dataclasses.replace(make_job("a 10 second clip", p, cat, seed=3),
                              direction=direction_of({**AX, "opener": "arc_orbit"}, "dice", pinned={"opener": 1}))
    assert opener_of(build_fallback(job, p, cat)) == "arc_orbit"
    import engine.director.fallback as fb
    real = fb.check

    def reject_arc(s, prof, c):                                  # the checker rejects the pinned opener
        if s["shots"][0]["camera"]["id"] == "arc_orbit":
            s = {**s, "shots": [{**s["shots"][0], "camera": {"id": "no_such_camera", "params": {}}}] + s["shots"][1:]}
        return real(s, prof, c)
    monkeypatch.setattr(fb, "check", reject_arc)
    s = build_fallback(job, p, cat)
    assert opener_of(s) == "low_hero_push" and any("opener request" in a for a in s["assumptions"])


def _markers(p, n):
    return [{"id": f"m{i}", "text": "look here", "anchor": {"space": "placed", "point": p.detailPoints[i]["point"]}}
            for i in range(n)]


def test_markers_still_get_detail_shots_with_the_new_opener():
    """Regression guard for the n_markers argument (a9cbdde)."""
    cat, p = Catalog.load(), _p("pocket_watch")
    job = dataclasses.replace(make_job("a 10 second clip", p, cat, seed=2, markers=_markers(p, 2)),
                              direction=direction_of({**AX, "opener": "arc_orbit"}, "dice"))
    s = build_fallback(job, p, cat)
    assert {(sh.get("target") or {}).get("marker") for sh in s["shots"]} >= {m["id"] for m in job.markers}


def test_both_pins_are_relaxed_one_at_a_time_before_both_are_dropped():
    from engine.director.fallback import DEFAULT_OPENER, _attempts
    both = direction_of({**AX, "pace": "calm", "opener": "arc_orbit"}, "dice", pinned={"pace": 1, "opener": 1})
    tries = _attempts(both, 3.0)
    keep_opener, keep_pace = ("medium", 0.0, True, "arc_orbit"), ("calm", 0.0, True, DEFAULT_OPENER)
    drop_both = ("medium", 0.0, True, DEFAULT_OPENER)
    assert tries.index(keep_opener) < tries.index(keep_pace) < tries.index(drop_both)
    assert ("medium", 0.0, False, "arc_orbit") in tries


def test_pinned_pace_survives_when_only_the_opener_fails(monkeypatch):
    """The checker rejects every arc_orbit opener: the fallback must keep the pinned calm pace (not fall
    to 'medium' + default opener) and record only the opener as adjusted."""
    import engine.director.fallback as fb
    from engine.director.floor import cadence_ok
    real = fb.check

    def no_arc_opener(s, p, c):
        r = real(s, p, c)
        if s["shots"][0]["camera"]["id"] == "arc_orbit":
            return dataclasses.replace(r, ok=False)
        return r
    monkeypatch.setattr(fb, "check", no_arc_opener)
    cat, p = Catalog.load(), _p("pocket_watch")
    d = direction_of({**AX, "pace": "calm", "opener": "arc_orbit"}, "dice", pinned={"pace": 1, "opener": 1})
    s = build_fallback(dataclasses.replace(make_job("a 10 second clip", p, cat, seed=3), direction=d), p, cat)
    assert s["edit"]["params"]["pace"] == "calm" and cadence_ok(s, "calm", cat)
    lines = [a for a in s["assumptions"] if "did not pass the quality checks" in a]
    assert len(lines) == 1 and "opener" in lines[0]


def test_unpinned_attempts_are_unchanged():
    from engine.director.fallback import DEFAULT_OPENER, _attempts
    d = direction_of({**AX, "opener": "arc_orbit"}, "dice")
    assert _attempts(d, 2.0) == [("medium", 2.0, True, "arc_orbit"), ("medium", 0.0, True, "arc_orbit"),
                                 ("medium", 0.0, True, DEFAULT_OPENER), ("medium", 0.0, False, DEFAULT_OPENER)]
