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


@pytest.mark.parametrize("seed", [2, 7, 11])
def test_no_tree_shades_the_subject_or_its_foreground_from_a_low_sun(seed):
    """Round 7: at 8 degrees the golden sun ran through a treeline and the whole clearing stood in tree shadow
    (real_r6_field_golden: rays from the car toward the sun hit valora_field_tree_12/13/15)."""
    import math
    from engine.worlds.street_layout import segment_hits
    p = _p("sports_car")
    cx, cy, _ = p.center
    cams = [(cx + 3.4, cy - 5.9, 0.55), (cx - 4.0, cy + 3.0, 0.4)]
    el = math.radians(8.0)
    for az in (0.0, 90.0, 200.0, 300.0):
        a = math.radians(az)
        sun = (math.cos(el) * math.cos(a), math.cos(el) * math.sin(a), math.sin(el))
        lay = F.layout(p, seed=seed, cameras=cams, hero=cams[0], sun=sun)
        paths = F.sun_paths(p, cams, sun)
        assert paths and lay["trees"]                          # the stands are thinned, not removed
        for x, y, h, *_ in lay["trees"]:
            w = F.TREE_CROWN_K * h
            assert not any(segment_hits(s0, s1, (x - w, y - w, 0.0), (x + w, y + w, h)) for s0, s1 in paths)
    assert F.sun_paths(p, cams, None) == [] and F.sun_paths(p, cams, (1.0, 0.0, 0.0)) == []


def test_trees_and_far_grass_never_move_the_blades():
    p = _p("sports_car")
    a = F.layout(p, seed=5)
    assert a["blades"] == F.layout(p, seed=5, hero=(p.center[0] + 5.0, p.center[1], 1.0))["blades"]


# ---- round 3 2026-09-25: ground contact (tyre patches pressed flat, tyre corridors, pressed stems)
def test_trample_is_flat_on_a_tyre_patch_and_standing_past_the_ramp():
    p = _p("sports_car")
    zones = F.tyre_zones(p)
    assert len(zones) == 4
    (zx, zy), _, ha, hl = zones[0]
    assert F.trample(zx, zy, zones) == pytest.approx(F.TRAMPLE_FLOOR)
    assert F.trample(zx + ha + F.TRAMPLE_RAMP_M + 0.01, zy, zones) == 1.0
    mid = F.trample(zx + ha + 0.5 * F.TRAMPLE_RAMP_M, zy, zones)
    assert F.TRAMPLE_FLOOR < mid < 1.0
    assert 0.15 <= F.TRAMPLE_RAMP_M <= 0.3
    assert F.tyre_zones(_p("mid_century_lounge_chair")) == []


def test_blades_by_a_tyre_lie_down_at_their_length():
    import math
    p = _p("sports_car")
    lay = F.layout(p, seed=3)
    zones = F.tyre_zones(p)
    near = [b for b in lay["blades"] if F._zone_dist(b[0], b[1], zones) < 0.3 * F.TRAMPLE_RAMP_M]   # under the body:
    assert near                                                                    # these stand just outside it
    for x, y, yaw, h, lean, *_ in near:
        assert h <= F.CLEAR_FLOOR * 0.45 * F.HEIGHT_JITTER[1] * F.trample(x, y, zones) + 1e-9
        assert lean > 1.0                                        # lying: its tip far out, not a stub
        assert math.hypot(h, lean * h) > 2.0 * h


def test_every_camera_keeps_a_corridor_to_each_tyre():
    p = _p("sports_car")
    cam = (p.center[0] + 6.0, p.center[1] - 3.0, 0.3)
    lines = F._sight_lines(p, [cam])
    assert len(lines) == 2 + len(p.wheels) and lines[-1][0] == "wedge"
    for (_, _, (wx, wy), aim, hw), w in zip(lines[1:-1], p.wheels):
        assert (wx, wy) == tuple(w["contact"][:2]) and aim == pytest.approx(F.WHEEL_AIM_K * w["radius"])
        assert hw == pytest.approx(F.WHEEL_SIGHT_K * w["radius"])


def test_pressed_stems_lie_under_a_wheeled_subject_only():
    p = _p("sports_car")
    lay = F.layout(p, seed=3)
    hx, hy = lay["footprint"]
    cx, cy = lay["centre"]
    assert len(lay["trample"]) > 500
    for x, y, yaw, length, pick in lay["trample"]:
        assert abs(x - cx) <= hx + 0.3 and abs(y - cy) <= hy + 0.3 and 0.0 < length < 0.6
    assert F.layout(_p("mid_century_lounge_chair"), seed=3)["trample"] == []
    assert F.layout(p, seed=3)["blades"] == lay["blades"]


def test_far_tufts_stop_growing():
    lay = F.layout(_p("sports_car"), seed=1)
    tallest = max(t[3] for t in lay["farGrass"])
    assert tallest <= 0.45 * F.HEIGHT_JITTER[1] * F.FAR_GROW_MAX + 1e-9


def test_the_wedge_keeps_the_whole_footprint_in_view():
    """A blade on the camera's ray to a bumper corner, outside the old fixed-width corridor, stays under the line."""
    p = _p("sports_car")
    cx, cy, _ = p.center
    cam = (cx + 12.0, cy - 12.0, 0.8)
    lines = F._sight_lines(p, [cam])
    half_w = max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest)
    corner = (cx + p.half[0], cy + p.half[1])                     # the far front corner, seen past the flank
    x, y = cam[0] + 0.8 * (corner[0] - cam[0]), cam[1] + 0.8 * (corner[1] - cam[1])
    assert F.sight_cap(x, y, lines[:1], half_w) == float("inf")   # the old corridor misses it
    cap = F.sight_cap(x, y, lines, half_w)
    assert 0.0 < cap < 0.8 * 0.35                                  # well under the camera: the line dips to the box
    assert F.sight_cap(cx - 6.0, cy + 6.0, lines, half_w) == float("inf")   # behind the subject: free


# ---- round 8 (owner's r7 grade: the grass overwhelmed the car, hid the tyres' contact, read as a diorama) --------
def test_worn_patches_open_the_field_and_the_crew_trod_the_foreground():
    import math
    p = _p("sports_car")
    cx, cy, _ = p.center
    cam = (cx + 3.4, cy - 5.9, 0.55)
    lay = F.layout(p, seed=7, cameras=[cam])
    strong = [(px, py) for px, py, pr, dp in lay["patches"] if dp > 0.6 and pr > 0.8
              and math.hypot(px - cam[0], py - cam[1]) > F.FORE_R_M]
    assert strong
    inside = sum(1 for b in lay["blades"] for px, py in strong if math.hypot(b[0] - px, b[1] - py) < 0.3)
    area = len(strong) * math.pi * 0.3 ** 2
    assert inside / area < 0.6 * F.DENSITY["grass"]                              # open ground in the patches
    for px, py, pr, dp in lay["patches"]:
        assert F.PATCH_R_M[0] <= pr <= F.PATCH_R_M[1] and F.PATCH_DEPTH[0] <= dp <= F.PATCH_DEPTH[1]
    near = [b for b in lay["blades"] if math.hypot(b[0] - cam[0], b[1] - cam[1]) < 0.5]
    assert near and max(b[3] for b in near) <= 0.45 * F.HEIGHT_JITTER[1] * (F.FORE_FLOOR + 0.1)
    assert F.fore_factor(cam[0], cam[1], [cam]) == F.FORE_FLOOR
    assert F.fore_factor(cam[0] + F.FORE_R_M, cam[1], [cam]) == 1.0
    assert F.patch_strength(cx + 100.0, cy, lay["patches"]) == 0.0


def test_grass_stands_in_clumps_of_different_heights():
    """Round 9 (owner: "uniform stems"): the height factor varies with position across CLUMP_RANGE, never above 1."""
    vals = [F.clump_factor(x * 0.13, y * 0.17, 7) for x in range(60) for y in range(60)]
    lo, hi = F.CLUMP_RANGE
    assert all(lo - 1e-9 <= v <= hi + 1e-9 for v in vals)
    assert max(vals) - min(vals) > 0.6 * (hi - lo)                  # tall clumps beside short ground
    assert F.clump_factor(1.0, 2.0, 7) == F.clump_factor(1.0, 2.0, 7) != F.clump_factor(1.0, 2.0, 8)


def test_the_boundary_fence_and_poles_stand_far_behind_the_subject():
    """Round 10: a post-and-wire fence FENCE_DIST_M behind the subject as the first camera sees it and a pole line
    further out; nothing near the subject, none without a camera, seeded."""
    import math
    p = _p("sports_car")
    cam = (4.4, -7.7, 0.55)
    b = F.boundary_props(p, 5, [cam])
    assert b == F.boundary_props(p, 5, [cam]) and F.boundary_props(p, 5, []) == {"posts": [], "wires": [], "poles": []}
    assert len(b["posts"]) > 20 and len(b["wires"]) == len(b["posts"]) - 1 and len(b["poles"]) == F.POLE_COUNT
    cx, cy = p.center[0], p.center[1]
    far = min(math.hypot(x - cx, y - cy) for x, y, *_ in b["posts"])
    assert far > 0.6 * F.FENCE_DIST_M
    for x, y, *_ in b["posts"] + b["poles"]:                  # behind the subject, never between it and the camera
        assert (x - cx) * (cx - cam[0]) + (y - cy) * (cy - cam[1]) > 0
