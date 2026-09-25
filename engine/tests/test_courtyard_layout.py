"""Task 63: rain_courtyard layout (engine/worlds/courtyard_layout.py), pure."""
import dataclasses

import pytest

from engine.catalog import Catalog
from engine.geometry import Pose, box_corners, project
from engine.tests.test_director_package import _p
from engine.worlds import courtyard_layout as C


def _rect_hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch", "sneaker", "mid_century_lounge_chair"])
@pytest.mark.parametrize("dressing", ["full", "sparse"])
def test_no_prop_in_the_subject_box_or_the_drive_lane(model, dressing):
    p = _p(model)
    lay = C.layout(p, seed=3, dressing=dressing, drive_lane_m=24.0)
    assert lay["props"]
    for pr in lay["props"]:
        r = C.footprint(pr)
        assert not _rect_hit(r, lay["exclusion"]), (pr["kind"], r)
        assert not _rect_hit(r, lay["lane"]), (pr["kind"], r)
    for leaf in lay["litter"]:
        x, y = leaf["xy"]
        e = lay["exclusion"]
        assert not (e[0] <= x <= e[2] and e[1] <= y <= e[3])


def test_no_lane_without_a_drive_lane():
    lay = C.layout(_p("sports_car"), seed=3, dressing="full", drive_lane_m=0.0)
    assert lay["lane"] == lay["exclusion"]


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch", "sneaker"])
def test_court_scales_with_the_subject(model):
    p = _p(model)
    lay = C.layout(p, seed=1, dressing="full", drive_lane_m=24.0)
    need = max(C.COURT_MIN_M, C.COURT_K * p.longest)
    assert lay["court"]["width"] >= need and lay["court"]["length"] >= need
    assert lay["exclusion"][0] <= p.boundsMin[0] and lay["exclusion"][3] >= p.boundsMax[1]


def test_same_seed_same_layout_other_seed_differs():
    p = _p("sports_car")
    a, b = C.layout(p, seed=5, dressing="full"), C.layout(p, seed=5, dressing="full")
    assert a == b and C.layout(p, seed=6, dressing="full") != a
    assert len(C.layout(p, seed=5, dressing="sparse")["props"]) < len(a["props"])


def _hero(p, cat):
    m = cat.get("camera", "low_hero_push")
    params = {k: v["default"] for k, v in m["params"].items()}
    params["lensMm"] = m["params"]["lensMm"]["min"]              # the widest this camera can be
    return cat.load_camera_path("low_hero_push")(params, p, 0.5, None)


@pytest.mark.parametrize("aspect", ["9:16", "16:9"])
def test_a_sneaker_sees_no_prop_from_the_hero_camera(aspect):
    cat, p = Catalog.load(), _p("sneaker")
    hero = _hero(p, cat)
    lay = C.layout(p, seed=2, dressing="full", hero=hero, aspect=aspect)
    for pr in lay["props"]:
        pts = [project(hero, c, aspect) for c in box_corners(*C.box(pr))]
        assert all(d <= 0 for _, _, d in pts), pr["kind"]           # wholly behind the hero camera
    unmoved = C.layout(p, seed=2, dressing="full", aspect=aspect)  # without the hero: the full court
    seen = [pr for pr in unmoved["props"]
            if any(d > 0 and abs(x) <= 1.02 and abs(y) <= 1.02
                   for x, y, d in (project(hero, c, aspect) for c in box_corners(*C.box(pr))))]
    assert seen, "the test must exercise the move: some prop is in view before it"


def test_a_car_keeps_its_set_dressing_in_place():
    cat, p = Catalog.load(), _p("sports_car")
    a = C.layout(p, seed=2, dressing="full", hero=_hero(p, cat))
    assert a == C.layout(p, seed=2, dressing="full")


def test_long_axis_follows_the_subject():
    p = _p("sports_car")
    q = dataclasses.replace(p, boundsMin=[p.boundsMin[1], p.boundsMin[0], p.boundsMin[2]],
                            boundsMax=[p.boundsMax[1], p.boundsMax[0], p.boundsMax[2]],
                            sizeM=[p.sizeM[1], p.sizeM[0], p.sizeM[2]])
    a, b = C.layout(p, seed=1, dressing="full"), C.layout(q, seed=1, dressing="full")
    ea, eb = a["lane"], b["lane"]
    assert (ea[2] - ea[0] > ea[3] - ea[1]) != (eb[2] - eb[0] > eb[3] - eb[1])
