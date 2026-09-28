"""Phase 6 lane C (Tasks 108-109), recipe steps 1-2: the cloth blocks' manifests and their pure maths."""
import math

import pytest

from engine.catalog import Catalog
from engine.physics import drape as D
from engine.tests.test_director_package import _p


@pytest.fixture(scope="module")
def cat():
    return Catalog.load()


# ---------------------------------------------------------------- T108 drape_reveal

def test_drape_reveal_manifest(cat):
    m = cat.get("sim", "drape_reveal")
    pr = m["params"]
    assert pr["fabric"]["values"] == ["silk", "satin", "canvas"] and pr["fabric"]["default"] == "silk"
    assert pr["pull"]["values"] == ["rear_to_front", "side", "up"] and pr["pull"]["default"] == "side"
    assert pr["colour"]["values"] == ["black", "charcoal", "ivory", "deep_red"]
    assert (pr["revealS"]["min"], pr["revealS"]["max"], pr["revealS"]["default"]) == (1.0, 4.0, 2.0)
    assert (pr["timeScale"]["min"], pr["timeScale"]["max"]) == (0.6, 1.0)
    assert m["capabilities"] == ["cloth.drape_reveal"] and m["tierMax"] == "T4"
    b = m["bake"]
    assert (b["method"], b["costClass"], b["prerollS"], b["maxFrames"]) == ("cloth_pc2", "heavy", 1.5, 240)
    assert b["cacheMBMax"] == 200 and b["estimateS"] <= 1200 and b["proxies"] == ["shell"]
    ph = m["physics"]
    assert ph["taxonomy"] == ["SC-02"] and ph["state"] == "baked" and ph["timeScaleParam"] == "timeScale"
    assert ph["windCalibration"]["perMs"] == 7600
    assert m["directorSelectable"] is False and m["landsIn"] == "Task 119"


def test_sheet_is_one_and_a_half_footprints_plus_the_height_under_the_budget():
    car = _p("sports_car")
    w, l = D.sheet_size(car)
    sx, sy, sz = car.sizeM
    assert math.isclose(w, 1.5 * sx + sz) and math.isclose(l, 1.5 * sy + sz)
    nx, ny, sp, gw, gl, c = D.sheet_grid(car)
    assert nx * ny <= 8000 and gw >= w - sp and gl >= l - sp
    assert sp >= 0.01 * max(car.sizeM)                                      # about 1% of the car, coarsened to 8k


def test_preshape_is_a_tent_that_never_touches_the_subject():
    nx = ny = 9
    h = [0.0] * 81
    h[4 * 9 + 4] = 1.0                                                        # a spike in the middle
    z = D.preshape(h, nx, ny, 0.01)
    assert all(zz >= hh + 0.01 - 1e-12 for zz, hh in zip(z, h))
    assert z[4 * 9 + 4] == pytest.approx(1.01)
    assert 0.01 < z[4 * 9 + 5] < 1.01 and z[0] >= 0.01                        # a slope, not a cliff


def test_pull_directions_and_pins():
    car = _p("sports_car")                                                    # long along y
    assert D.pull_dir("up", car) == (0.0, 0.0)
    assert D.pull_dir("rear_to_front", car, nose_sign=-1) == (0.0, -1.0)
    d = D.pull_dir("side", car, camera_xy=(0.0, -6.0))                        # camera in front (-y): right is +x
    assert d == pytest.approx((1.0, 0.0))
    assert D.pull_dir("side", car, camera_xy=(-3.0, -5.0)) == (1.0, 0.0)      # a 3/4 view still pulls across
    assert D.pull_dir("side", car, camera_xy=(0.0, 6.0)) == (-1.0, 0.0)
    nx, ny = 5, 4
    xy = [(i, j) for j in range(ny) for i in range(nx)]
    zs = [0.0] * 20
    assert D.pins("side", nx, ny, xy, zs, (1.0, 0.0)) == [4, 9, 14, 19]      # a short edge: both hands cover it
    assert D.pins("rear_to_front", nx, ny, xy, zs, (0.0, -1.0)) == [0, 1, 2, 3, 4]
    grips = D.pins("side", 3, 101, [(0, 0)] * 303, [0.0] * 303, (1.0, 0.0))
    assert [k // 3 for k in grips] == list(range(17, 34)) + list(range(67, 84))
    zs[2 * 5 + 2] = 1.0
    assert 12 in D.pins("up", nx, ny, xy, zs, (0.0, 0.0))


@pytest.mark.parametrize("pull", ["side", "rear_to_front", "up"])
def test_pull_keys_are_one_continuous_path_that_clears_by_reveal_plus_half(pull):
    car = _p("sports_car")
    nx, ny, sp, w, l, c = D.sheet_grid(car)
    d = D.pull_dir(pull, car, camera_xy=(0.0, -6.0), nose_sign=1)
    keys = D.pull_keys(pull, car, 46, 24, 2.0, d, (w, l), (2.0, 0.0, 0.02))
    frames = [f for f, _ in keys]
    assert frames == list(range(46, 46 + len(frames))) and frames[-1] == 46 + math.ceil(2.5 * 24)
    longer = D.pull_keys(pull, car, 46, 24, 2.0, d, (w, l), (2.0, 0.0, 0.02), end_s=4.0)
    assert longer[:len(keys)] == keys and longer[-1][0] == 46 + 96                # keeps walking to the bake end
    assert math.dist(longer[-1][1][:2], (0, 0)) >= math.dist(keys[-1][1][:2], (0, 0)) - 1e-9
    offs = [o for _, o in longer]
    assert offs[0] == (0.0, 0.0, 0.0)
    steps = [math.dist(a, b) for a, b in zip(offs, offs[1:])]
    assert max(steps) * 24 < 12.0                                             # under 3 x maxSpeedMs, no jump
    end = offs[-1]
    if pull == "up":
        assert end[2] >= car.sizeM[2] + 0.5 * max(w, l)
    else:
        along = abs(end[0] * d[0] + end[1] * d[1])
        assert along >= (w if abs(d[0]) > 0 else l)                          # the trailing edge is past the subject


def test_off_subject_share():
    car = _p("sports_car")
    assert D.off_subject_share([(0.0, 0.0, 0.5)], car) == 1.0
    assert D.off_subject_share([(10.0, 0.0, 0.5), (0.0, 0.0, 0.5)], car) == 0.5


# ---------------------------------------------------------------- T109 flag and silk_ribbon

from engine.physics import cloth_waves as W  # noqa: E402


def test_flag_and_ribbon_manifests_are_stateless_cloth(cat):
    f, r = cat.get("sim", "flag"), cat.get("sim", "silk_ribbon")
    assert f["bake"] == {"method": "none", "costClass": "cheap"} and r["bake"] == {"method": "none", "costClass": "cheap"}
    assert f["capabilities"] == ["cloth.flag"] and r["capabilities"] == ["cloth.ribbon"]
    assert f["physics"]["taxonomy"] == ["SC-01"] and r["physics"]["taxonomy"] == ["SC-05"]
    assert f["physics"]["requiresWorld"] == {"outdoor": True} and f["physics"]["windDriven"] is True
    assert (r["params"]["widthFrac"]["min"], r["params"]["widthFrac"]["max"]) == (0.03, 0.10)
    for m in (f, r):
        assert m["directorSelectable"] is False and m["landsIn"] == "Task 119"


def test_flag_hangs_in_calm_air_and_flies_out_in_wind():
    calm = W.flag_positions(1.0, 0.0, 0.0, (0.0, 0.0), 7, 3.0)
    windy = W.flag_positions(1.0, 8.0, 0.0, (0.0, 0.0), 7, 3.0)
    fly = W.FLAG_NX - 1                                               # top row, fly end
    assert abs(calm[fly][0]) < 0.2 and calm[fly][2] < 3.0 - 1.0        # hangs down the pole
    assert windy[fly][0] > 1.3 and abs(windy[fly][2] - (3.0 - 0.05)) < 0.35   # blows out downwind (+x)
    assert len(windy) == W.FLAG_NX * W.FLAG_NY


def test_flag_flutter_rises_with_wind_and_the_pole_edge_stays_put():
    assert W.flag_frequency(10.0) > W.flag_frequency(3.0) > 0 == W.flag_frequency(0.0)
    a = W.flag_positions(0.0, 6.0, 90.0, (1.0, 2.0), 3, 3.0)
    b = W.flag_positions(0.37, 6.0, 90.0, (1.0, 2.0), 3, 3.0)
    for j in range(W.FLAG_NY):                                         # u = 0 column is on the pole
        k = j * W.FLAG_NX
        assert a[k] == pytest.approx(b[k]) and a[k][0] == pytest.approx(1.0) and a[k][1] == pytest.approx(2.0)
    assert max(abs(p[0] - q[0]) for p, q in zip(a, b)) > 0.02         # the rest ripples


def test_flag_pole_keeps_the_flag_clear_of_the_subject():
    car = _p("sports_car")
    pole = W.flag_pole_xy(car, (0.0, -7.0), 0.0)
    assert pole[1] > car.boundsMax[1]                                  # behind the car from the camera
    for t in (0.0, 0.5, 1.3):
        for d in (0.0, 90.0, 180.0, 270.0):
            assert W.clear_of_subject(W.flag_positions(t, 12.0, d, pole, 5, W.pole_height(car)), car)
    assert W.pole_height(car) == pytest.approx(2.2 * car.sizeM[2]) and W.pole_height(_p("pocket_watch")) == 2.5


@pytest.mark.parametrize("subject", ["sports_car", "pocket_watch", "sneaker"])
def test_ribbon_stays_outside_the_subject_and_above_the_ground(subject):
    prof = _p(subject)
    for t in (0.0, 0.7, 2.9, 6.1):
        v, faces = W.ribbon_positions(t, prof, 0.10, 0.3, 11, camera_xy=(0.0, -5.0))
        assert len(v) == 2 * W.RIBBON_N and len(faces) == W.RIBBON_N - 1
        assert W.clear_of_subject(v, prof, margin=0.0)
        assert min(p[2] for p in v) > 0.0
        widths = [math.dist(v[2 * i], v[2 * i + 1]) for i in range(W.RIBBON_N)]
        assert max(widths) <= 0.10 * prof.sizeM[2] * 1.0001              # at most widthFrac x height


def test_ribbon_passes_lower_on_the_camera_side():
    car = _p("sports_car")
    (cx, cy), a, b, zc, tilt, cam = W.ribbon_loop(car, 0.08, camera_xy=(0.0, -6.0))
    assert tilt > 0 and cam == pytest.approx(-math.pi / 2)


def test_small_subjects_simulate_at_a_metre():
    assert D.sim_scale(_p("sports_car")) == 1.0
    assert D.sim_scale(_p("pocket_watch")) == pytest.approx(1.0 / max(_p("pocket_watch").sizeM))
