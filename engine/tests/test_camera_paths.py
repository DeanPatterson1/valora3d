import json
import math
from pathlib import Path
from engine.catalog import Catalog
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))


def _defaults(cat, bid):
    return {k: v["default"] for k, v in cat.get("camera", bid)["params"].items()}


def test_low_hero_push_moves_closer_and_stays_low():
    cat = Catalog.load()
    sample = cat.load_camera_path("low_hero_push")
    p = _defaults(cat, "low_hero_push")
    a, b = sample(p, CAR, 0.0), sample(p, CAR, 1.0)
    da = math.dist(a.position, CAR.center)
    db = math.dist(b.position, CAR.center)
    assert db < da
    assert a.position[2] <= 0.6 * CAR.sizeM[2]
    assert a.target == CAR.center and a.lens_mm == p["lensMm"]


def test_arc_orbit_sweeps_azimuth_at_constant_distance():
    cat = Catalog.load()
    sample = cat.load_camera_path("arc_orbit")
    p = _defaults(cat, "arc_orbit")
    a, b = sample(p, CAR, 0.0), sample(p, CAR, 1.0)
    assert abs(math.dist(a.position, CAR.center) - math.dist(b.position, CAR.center)) < 1e-9
    az = lambda q: math.degrees(math.atan2(q.position[1], q.position[0]))
    assert abs((az(b) - az(a)) - p["sweepDeg"]) < 1e-6


def test_settle_frac_holds_the_camera_still_at_the_end():
    cat = Catalog.load()
    for bid in ("low_hero_push", "arc_orbit"):
        sample = cat.load_camera_path(bid)
        p = {**_defaults(cat, bid), "settleFrac": 0.25}
        assert sample(p, CAR, 0.8).position == sample(p, CAR, 1.0).position, bid


def test_paths_accept_an_ignored_target_argument():
    cat = Catalog.load()
    for bid in ("low_hero_push", "arc_orbit"):
        sample = cat.load_camera_path(bid)
        p = _defaults(cat, bid)
        assert sample(p, CAR, 0.5, None) == sample(p, CAR, 0.5)
