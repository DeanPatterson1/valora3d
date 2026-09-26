"""Round 6 (2026-09-25): outdoors the reflection rig keeps no studio cards (the overhead and strips burnt the night
street's windshield, bonnet and intake white) and its rim drops to a low, dim edge light."""
import math

from engine.blocks.lighting.reflection_rig.build import NIGHT_KEY_EV, OUTDOOR_RIM, REFLECTION_ONLY_ROLES, _outdoor
from engine.catalog import Catalog
from engine.reflect import rig_layout
from engine.tests.test_director_package import _p


def _layout(p):
    params = {k: v["default"] for k, v in Catalog.load().get("lighting", "reflection_rig")["params"].items()}
    cam = (p.center[0] + 1.0, p.center[1] - 6.0, 0.45)
    return rig_layout(p, cam, params)


def test_outdoors_the_studio_cards_are_dropped_and_the_rest_kept():
    p = _p("sports_car")
    full = _layout(p)
    out = _outdoor(full, p)
    assert not [s for s in out.lights if s.role in REFLECTION_ONLY_ROLES]
    assert {s.role for s in out.lights} == {s.role for s in full.lights} - set(REFLECTION_ONLY_ROLES)
    assert out.ambient == full.ambient


def test_the_outdoor_rim_is_low_dim_and_as_far_away():
    p = _p("sports_car")
    full = _layout(p)
    rim0 = next(s for s in full.lights if s.role == "rim")
    rim = next(s for s in _outdoor(full, p).lights if s.role == "rim")
    d = math.dist(rim.center, p.center)
    assert d == math.dist(rim0.center, p.center) or abs(d - math.dist(rim0.center, p.center)) < 1e-9
    el = math.degrees(math.asin((rim.center[2] - p.center[2]) / d))
    assert abs(el - OUTDOOR_RIM["elevationDeg"]) < 1e-6 and rim.power == rim0.power * OUTDOOR_RIM["power"]
    to_c = tuple(b - a for a, b in zip(rim.center, p.center))
    assert sum(f * t for f, t in zip(rim.facing, to_c)) > 0
    assert 1.0 <= NIGHT_KEY_EV <= 2.0
