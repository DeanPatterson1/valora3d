"""TG-47 premium-look defaults (owner-delegated look call, 2026-09-25) and outdoor held-variety structure."""
import pytest

from engine.director.fallback import (PREMIUM_CAM_M, PREMIUM_DETAIL_MM, PREMIUM_FSTOP, PREMIUM_LENS_MM,
                                      _hero_push, _reorder_middle, _width_frac)
from engine.tests.test_director_fallback_phase5 import _fb


def _cam_z(cat, sh, p, u):
    prm = {k: v["default"] for k, v in cat.get("camera", sh["camera"]["id"])["params"].items()}
    prm.update(sh["camera"]["params"])
    return cat.load_camera_path(sh["camera"]["id"])(prm, p, u).position[2]


@pytest.mark.parametrize("world", ["night_street", "rain_courtyard", "golden_field"])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_an_outdoor_car_is_shot_low_long_and_sharp(world, seed):
    s, p, cat, _ = _fb("sports_car", seed=seed, world=world)
    for i in (0, len(s["shots"]) - 1):
        sh = s["shots"][i]
        prm = sh["camera"]["params"]
        assert prm["fstop"] == PREMIUM_FSTOP and PREMIUM_LENS_MM[0] <= prm["lensMm"] <= PREMIUM_LENS_MM[1], (i, prm)
        z = _cam_z(cat, sh, p, 1.0 if i else 0.0)
        assert PREMIUM_CAM_M[0] - 0.05 <= z <= PREMIUM_CAM_M[1] + 0.05, (i, z)     # low, not a high 3/4
    for sh in s["shots"]:
        if sh["camera"]["id"] == "macro_detail":
            assert sh["camera"]["params"]["lensMm"] == PREMIUM_DETAIL_MM


def test_the_hero_fills_about_82_percent_of_the_width():
    s, p, cat, _ = _fb("sports_car", seed=0, world="night_street")
    sh = s["shots"][-1]
    prm = {k: v["default"] for k, v in cat.get("camera", sh["camera"]["id"])["params"].items()}
    prm.update(sh["camera"]["params"])
    f = _width_frac(cat.load_camera_path(sh["camera"]["id"]), prm, p, s["format"]["aspect"], 1.0)
    assert f is not None and 0.78 <= f <= 0.85       # the silhouette, not the box (round 7), 1.5% edge margin


@pytest.mark.parametrize("world", ["rain_courtyard", "golden_field"])
def test_the_hook_width_is_the_silhouette_not_the_box(world):
    """Round 7: the width a car fills is its projected mesh (the surface samples' hull), and the checker keeps a
    distance whose silhouette is in frame even when the bounds box corners are not (round 6 sat at ~0.74)."""
    from engine.geometry import box_corners, project
    s, p, cat, _ = _fb("sports_car", seed=0, world=world)
    sh = s["shots"][0]
    prm = {k: v["default"] for k, v in cat.get("camera", sh["camera"]["id"])["params"].items()}
    prm.update(sh["camera"]["params"])
    sample = cat.load_camera_path(sh["camera"]["id"])
    f = _width_frac(sample, prm, p, s["format"]["aspect"], 0.0)
    assert 0.78 <= f <= 0.85, f
    pose = sample(prm, p, 0.0)
    xs = [project(pose, c, s["format"]["aspect"])[0] for c in box_corners(p.boundsMin, p.boundsMax)]
    assert (max(xs) - min(xs)) / 2 > f + 0.05          # the box overstates the width the car fills


def test_the_checker_frames_the_silhouette_not_the_box():
    """A low 3/4 hero whose box corners leave the 9:16 frame but whose silhouette does not is 'ok' as is."""
    from engine.checker import _shot_verdict
    from engine.geometry import box_corners, frame_stats
    _, p, cat, _ = _fb("sports_car", seed=0, world="rain_courtyard")
    spec = cat.get("camera", "low_hero_push")["params"]
    prm = {**{k: v["default"] for k, v in spec.items()}, "azimuthDeg": -58, "lensMm": 40, "heightFrac": 0.323,
           "pushFrac": 0.0, "distance": 3.5}
    sample = cat.load_camera_path("low_hero_push")
    assert not frame_stats(sample(prm, p, 0.0), box_corners(p.boundsMin, p.boundsMax), "9:16")["inFrame"]
    assert _shot_verdict(sample, prm, p, "full", "9:16") == "out"                           # the box (studio)
    assert _shot_verdict(sample, prm, p, "full", "9:16", silhouette=True) == "ok"
    assert _shot_verdict(sample, {**prm, "distance": 2.7}, p, "full", "9:16", silhouette=True) == "out"  # body crops


def test_a_wet_world_gets_a_mirror_ground():
    s, _, _, _ = _fb("sports_car", seed=0, world="night_street", weather="wet")
    wet = [e for e in s["effects"] if e["id"] == "wet_surface"]
    assert wet and wet[0]["params"]["wetness"] == 1.0 and 0.6 <= wet[0]["params"]["puddles"] <= 0.8


def test_products_and_the_studio_are_not_premium_cars():
    s, _, _, _ = _fb("pocket_watch", seed=0, world="night_street")
    assert all(sh["camera"]["params"].get("fstop") != PREMIUM_FSTOP or sh["camera"]["id"] == "macro_detail"
               for sh in s["shots"][:1])
    st, _, _, _ = _fb("sports_car", seed=0, world="studio_cyc")
    assert st["shots"][0]["camera"]["params"]["fstop"] == 8.0            # phase 4's vehicle f/8 in the studio


def _shots(ids):
    return [{"startS": float(i), "endS": float(i + 1) if i else 3.0, "purpose": p, "focus": "subject",
             "camera": {"id": c, "params": {"move": "slide"} if c == "macro_detail" else {}}}
            for i, (p, c) in enumerate(ids)]


def test_middle_order_flips_on_a_seeded_coin_and_keeps_the_cut_times():
    base = [("hook", "arc_orbit"), ("detail", "macro_detail"), ("motion", "arc_orbit"), ("hero", "arc_orbit")]
    flips = 0
    for seed in range(20):
        sh = _shots(base)
        times = [(x["startS"], x["endS"]) for x in sh]
        _reorder_middle(sh, seed)
        assert [(x["startS"], x["endS"]) for x in sh] == times
        flips += sh[1]["purpose"] == "motion"
    assert 0 < flips < 20


def test_the_hero_push_lands_where_the_arc_would():
    from engine.catalog import Catalog
    cat = Catalog.load()
    seed = next(k for k in range(50) if __import__("random").Random(f"detail:{k}:hero").random() < 0.5)
    sh = _shots([("hook", "arc_orbit"), ("hero", "arc_orbit")])
    sh[-1]["camera"]["params"] = {"startAzimuthDeg": 60.0, "sweepDeg": -30.0, "settleFrac": 0.4, "lensMm": 55.0}
    _hero_push(sh, seed, cat)
    q = sh[-1]["camera"]
    assert q["id"] == "low_hero_push" and q["params"]["azimuthDeg"] == 30.0 and q["params"]["settleFrac"] == 0.4
