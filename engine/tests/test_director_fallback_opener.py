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
