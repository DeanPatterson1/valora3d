"""Task 70: night_street layout (engine/worlds/street_layout.py), pure."""
import dataclasses

import pytest

from engine.catalog import Catalog
from engine.tests.test_director_package import _p
from engine.worlds import street_layout as S


def _rect(it):
    return (it["min"][0], it["min"][1], it["max"][0], it["max"][1])


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch", "sneaker", "mid_century_lounge_chair"])
@pytest.mark.parametrize("seed", [1, 2, 7])
def test_nothing_in_the_subject_box_or_the_drive_lane(model, seed):
    lay = S.layout(_p(model), seed=seed, lane_m=30.0)
    assert lay["lamps"] and lay["facades"]
    for it in lay["lamps"] + lay["facades"] + lay["neon"] + lay["kerbs"]:
        assert not _hit(_rect(it), lay["exclusion"]), it["kind"]
        assert not _hit(_rect(it), lay["lane"]), it["kind"]


def test_same_seed_same_layout_other_seed_differs():
    p = _p("sports_car")
    a = S.layout(p, seed=5)
    assert a == S.layout(p, seed=5) and S.layout(p, seed=6) != a


@pytest.mark.parametrize("seed", range(40))
def test_neon_count_and_lamp_spacing_are_in_range(seed):
    lay = S.layout(_p("sports_car"), seed=seed)
    assert 0 <= len(lay["neon"]) <= S.NEON_MAX
    lo, hi = S.FACADE_W
    for f in lay["facades"]:
        assert f["v1"] - f["v0"] <= hi + 1e-9 and S.FACADE_H[0] <= f["height"] <= S.FACADE_H[1]
    along = 1 if lay["road"]["alongAxis"] == "y" else 0
    vs = sorted(it["head"][along] for it in lay["lamps"])
    gaps = [b - a for a, b in zip(vs, vs[1:])]
    assert all(S.LAMP_GAP[0] - 1e-9 <= g <= S.LAMP_GAP[1] + 1e-9 for g in gaps), gaps


def test_neon_is_used_across_seeds():
    counts = {len(S.layout(_p("sports_car"), seed=s)["neon"]) for s in range(40)}
    assert max(counts) >= 2 and len(counts) >= 3                        # the seeded range is exercised
    assert max(counts) <= S.NEON_MAX


@pytest.mark.parametrize("model", ["sports_car", "sneaker", "pocket_watch"])
def test_the_street_scales_with_the_subject(model):
    p = _p(model)
    lay = S.layout(p, seed=1)
    assert lay["road"]["length"] >= max(30.0, 8 * p.longest) - 1e-9
    assert lay["road"]["width"] >= max(S.ROAD_MIN_M, S.ROAD_K * p.longest) - 1e-9


def test_no_lane_without_a_drive_lane():
    lay = S.layout(_p("sports_car"), seed=3, lane_m=0.0)
    assert lay["lane"] == lay["exclusion"]


def _hero(p, cat):
    m = cat.get("camera", "low_hero_push")
    params = {k: v["default"] for k, v in m["params"].items()}
    params["lensMm"] = m["params"]["lensMm"]["min"]              # the widest this camera can be
    return cat.load_camera_path("low_hero_push")(params, p, 0.5, None)


@pytest.mark.parametrize("model", ["sneaker", "pocket_watch"])
@pytest.mark.parametrize("aspect", ["9:16", "16:9"])
@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_a_small_subject_sees_at_most_one_lamp(model, aspect, seed):
    cat, p = Catalog.load(), _p(model)
    hero = _hero(p, cat)
    lay = S.layout(p, seed=seed, hero=hero, aspect=aspect)
    assert sum(S.seen(hero, it, aspect) for it in lay["lamps"]) <= 1
    far = S.layout(p, seed=seed, aspect=aspect)
    assert far["road"]["faceU"] > S.layout(_p("sports_car"), seed=seed)["road"]["faceU"] - 1e-9  # pushed back


def _down_the_road(p):
    """A low camera 14 m down the road looking along it: the pose that sees the most lamp posts."""
    from engine.geometry import Pose
    along = 1 if S.layout(p, seed=1)["road"]["alongAxis"] == "y" else 0
    pos, tgt = list(p.center), list(p.center)
    pos[along] -= 14.0
    pos[2] = 0.3
    tgt[along] += 10.0
    return Pose(tuple(pos), tuple(tgt), 24.0)


def test_the_small_subject_rule_is_exercised_and_holds():
    """Unmoved, a sneaker's street shows two lamps down the road for some seed; with that hero pose the
    layout moves all but one behind the camera."""
    p = _p("sneaker")
    down = _down_the_road(p)
    before = [sum(S.seen(down, it, "16:9") for it in S.layout(p, seed=s, aspect="16:9")["lamps"]) for s in range(1, 10)]
    after = [sum(S.seen(down, it, "16:9") for it in S.layout(p, seed=s, hero=down, aspect="16:9")["lamps"])
             for s in range(1, 10)]
    assert max(before) >= 2 and max(after) <= 1


def test_a_car_keeps_its_lamps_in_place():
    cat, p = Catalog.load(), _p("sports_car")
    a = S.layout(p, seed=2, hero=_hero(p, cat))
    b = S.layout(p, seed=2)
    assert a["lamps"] == b["lamps"]


def test_long_axis_follows_the_subject():
    p = _p("sports_car")
    q = dataclasses.replace(p, boundsMin=[p.boundsMin[1], p.boundsMin[0], p.boundsMin[2]],
                            boundsMax=[p.boundsMax[1], p.boundsMax[0], p.boundsMax[2]],
                            sizeM=[p.sizeM[1], p.sizeM[0], p.sizeM[2]])
    assert S.layout(p, seed=1)["road"]["alongAxis"] != S.layout(q, seed=1)["road"]["alongAxis"]


def test_nothing_stands_in_the_camera_clear_zone():
    p = _p("sports_car")
    base = S.layout(p, seed=4)
    lamp = base["lamps"][0]
    cam = tuple((a + b) / 2 for a, b in zip(lamp["min"], lamp["max"]))       # a camera key inside a lamp post
    lay = S.layout(p, seed=4, cameras=[cam])
    assert lamp not in lay["lamps"] and len(lay["lamps"]) == len(base["lamps"]) - 1
    for it in lay["lamps"] + lay["neon"] + lay["facades"]:
        assert not S._near(it, cam, S.CAM_CLEAR_M)


def test_nothing_stands_between_a_camera_and_the_subject():
    p = _p("sports_car")
    base = S.layout(p, seed=4)
    fa = base["facades"][0]
    mid = tuple((a + b) / 2 for a, b in zip(fa["min"], fa["max"]))
    c = tuple(p.center)
    cam = (2 * mid[0] - c[0], 2 * mid[1] - c[1], 1.0)          # beyond the facade: it blocks the view
    lay = S.layout(p, seed=4, cameras=[cam])
    assert fa not in lay["facades"]
    for it in lay["lamps"] + lay["neon"] + lay["facades"]:
        assert not any(S.segment_hits(cam, q, it["min"], it["max"]) for q in S._sight(p))


def test_segment_hits():
    assert S.segment_hits((0, 0, 0), (10, 0, 0), (4, -1, -1), (5, 1, 1))
    assert not S.segment_hits((0, 0, 0), (3, 0, 0), (4, -1, -1), (5, 1, 1))
    assert not S.segment_hits((0, 5, 0), (10, 5, 0), (4, -1, -1), (5, 1, 1))
