"""Task 71: golden_field layout (engine/worlds/field_layout.py), pure."""
import pytest

from engine.tests.test_director_package import _p
from engine.worlds import field_layout as F


@pytest.mark.parametrize("model", ["sports_car", "mid_century_lounge_chair", "sneaker"])
@pytest.mark.parametrize("track", [False, True])
def test_no_blade_root_in_the_footprint(model, track):
    p = _p(model)
    lay = F.layout(p, seed=3, track=track)
    assert lay["blades"]
    lo, hi = p.boundsMin, p.boundsMax
    for x, y, *_ in lay["blades"]:
        assert not (lo[0] - F.BLADE_W <= x <= hi[0] + F.BLADE_W and lo[1] - F.BLADE_W <= y <= hi[1] + F.BLADE_W)


@pytest.mark.parametrize("model", ["sports_car", "sneaker", "mid_century_lounge_chair"])
def test_the_clearing_scales_with_the_subject_and_tapers(model):
    p = _p(model)
    lay = F.layout(p, seed=1, grass_height_m=0.45)
    cx, cy = lay["centre"]
    hx, hy = lay["footprint"]
    assert lay["clearing"]["in"] == pytest.approx(F.CLEAR_IN * max(hx, hy))
    near = [b for b in lay["blades"] if max(abs(b[0] - cx) / hx, abs(b[1] - cy) / hy) <= F.CLEAR_IN]
    far = [b for b in lay["blades"] if max(abs(b[0] - cx) / hx, abs(b[1] - cy) / hy) >= F.CLEAR_OUT]
    assert near and far
    assert max(b[3] for b in near) <= F.CLEAR_FLOOR * 0.45 * F.HEIGHT_JITTER[1] + 1e-9
    assert max(b[3] for b in far) > 0.45                      # full height out there
    a, b = F.layout(_p("sneaker"), seed=1)["clearing"]["in"], F.layout(_p("sports_car"), seed=1)["clearing"]["in"]
    assert b > 5 * a


def test_blades_near_the_subject_lean_away_from_it():
    p = _p("sports_car")
    lay = F.layout(p, seed=2)
    cx, cy = lay["centre"]
    hx, hy = lay["footprint"]
    import math
    for x, y, yaw, *_ in lay["blades"]:
        if max(abs(x - cx) / hx, abs(y - cy) / hy) < F.CLEAR_OUT:
            out = (x - cx, y - cy)
            d = (math.cos(math.radians(yaw)), math.sin(math.radians(yaw)))
            assert out[0] * d[0] + out[1] * d[1] > 0


def test_the_track_is_clear_of_blades():
    p = _p("sports_car")
    lay = F.layout(p, seed=4, track=True)
    x0, y0, x1, y1 = lay["track"]
    assert (y1 - y0 > x1 - x0) == (p.half[1] >= p.half[0])      # along the subject's longer axis
    assert not any(x0 <= b[0] <= x1 and y0 <= b[1] <= y1 for b in lay["blades"])
    assert any(x0 <= b[0] <= x1 and y0 <= b[1] <= y1 for b in F.layout(p, seed=4)["blades"])   # it matters
    assert F.layout(p, seed=4)["track"] is None


def test_same_seed_same_field():
    p = _p("sports_car")
    a = F.layout(p, seed=5)
    assert a == F.layout(p, seed=5) and F.layout(p, seed=6) != a


def test_extent_and_cap():
    for model in ("sports_car", "sneaker"):
        p = _p(model)
        lay = F.layout(p, seed=1)
        assert lay["extent"] == max(40.0, 10.0 * p.longest) and len(lay["blades"]) <= F.BLADE_CAP


def test_wildflowers_carry_flowers():
    lay = F.layout(_p("sports_car"), seed=1, crop="wildflowers")
    share = sum(1 for b in lay["blades"] if b[5]) / len(lay["blades"])
    assert 0.04 < share < 0.12
    assert not any(b[5] for b in F.layout(_p("sports_car"), seed=1, crop="grass")["blades"])


def test_blades_never_stand_in_a_cameras_sight_line():
    p = _p("mid_century_lounge_chair")
    cx, cy, _ = p.center
    cam = (cx + 2.0, cy + 1.0, 0.08)                              # a low hero camera inside the grass
    lay = F.layout(p, seed=1, cameras=[cam])
    lines = F._sight_lines(p, [cam])
    half_w = max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest)
    assert lay["sightCut"] > 0
    for x, y, _, h, *_ in lay["blades"]:
        assert h <= F.sight_cap(x, y, lines, half_w) + 1e-9
    assert sum(b[3] for b in lay["blades"]) < sum(b[3] for b in F.layout(p, seed=1)["blades"])


def test_the_blade_disc_edge_tapers():
    p = _p("sports_car")
    lay = F.layout(p, seed=1)
    cx, cy = lay["centre"]
    import math
    rim = [b[3] for b in lay["blades"] if math.hypot(b[0] - cx, b[1] - cy) > 0.98 * lay["bladeRadius"]]
    at = 1.0 - (1.0 - F.EDGE_FLOOR) * (0.98 - (1.0 - F.EDGE_TAPER)) / F.EDGE_TAPER
    assert rim and max(rim) <= 0.45 * F.HEIGHT_JITTER[1] * at + 1e-9


# ---- art pass 2026-09-25: static far grass / cover and tree stands (pure layout parts of the photo field)
def test_far_grass_and_cover_respect_the_footprint_the_track_and_every_sight_line():
    import math
    p = _p("mid_century_lounge_chair")
    cx, cy, _ = p.center
    cam = (cx + 2.0, cy + 1.0, 0.08)                              # a low hero camera inside the grass
    lay = F.layout(p, seed=1, track=True, cameras=[cam])
    lines = F._sight_lines(p, [cam])
    half_w = max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest)
    hx, hy = lay["footprint"]
    x0, y0, x1, y1 = lay["track"]
    assert len(lay["farGrass"]) > 1000 and len(lay["farGrass"]) <= F.FAR_CAP
    for x, y, _, h, w in lay["farGrass"]:
        assert h <= F.sight_cap(x, y, lines, half_w) + 1e-9
        assert not (x0 <= x <= x1 and y0 <= y <= y1)
        assert abs(x - cx) > hx + F.COVER_PAD_M or abs(y - cy) > hy + F.COVER_PAD_M
        inside = math.hypot(x - cx, y - cy) < lay["bladeRadius"]
        assert w >= h - 1e-9 and (not inside or h <= F.COVER_K * 0.45 * F.HEIGHT_JITTER[1] + 1e-9)


def test_tree_stands_stand_past_every_camera_and_out_of_every_sight_line():
    import math
    from engine.worlds.street_layout import segment_hits
    p = _p("sports_car")
    cx, cy, _ = p.center
    cams = [(cx + 6.0, cy + 1.0, 1.2), (cx - 3.0, cy - 7.0, 0.3)]
    lay = F.layout(p, seed=2, cameras=cams, hero=cams[0])
    far = max(math.hypot(c[0] - cx, c[1] - cy) for c in cams)
    assert lay["trees"]
    for x, y, h, *_ in lay["trees"]:
        assert math.hypot(x - cx, y - cy) >= far + F.TREE_CAM_PAD_M - 1e-9
        w = F.TREE_CROWN_K * h
        assert not any(segment_hits(c, tuple(p.center), (x - w, y - w, 0.0), (x + w, y + w, h)) for c in cams)
    back = math.atan2(cy - cams[0][1], cx - cams[0][0])          # the first stand is in the hero's background
    ang = [abs((math.atan2(y - cy, x - cx) - back + math.pi) % math.tau - math.pi) for x, y, *_ in lay["trees"]]
    assert min(ang) < math.radians(F.TREE_HERO_CONE_DEG + 20.0)


def test_trees_and_far_grass_never_move_the_blades():
    p = _p("sports_car")
    a = F.layout(p, seed=5)
    assert a["blades"] == F.layout(p, seed=5, hero=(p.center[0] + 5.0, p.center[1], 1.0))["blades"]
