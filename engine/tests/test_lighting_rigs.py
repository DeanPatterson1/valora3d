"""Task 72: the pure layouts of hard_sun, rim_neon and hdri_only."""
import math

import pytest

from engine.lighting import rigs as R
from engine.tests.test_director_package import _p


def _hero(p):
    cx, cy, cz = p.center
    return (cx + 3 * p.radius, cy, cz)


def test_sun_vector_zero_is_behind_the_subject():
    p = _p("sports_car")
    v = R.sun_vector(p, _hero(p), 0.0, 10.0)
    assert v[0] < 0 and abs(v[1]) < 1e-9 and v[2] == pytest.approx(math.sin(math.radians(10.0)))
    s = R.sun_vector(p, _hero(p), 90.0, 10.0)
    assert abs(s[0]) < 1e-9 and s[1] > 0 and s[2] > 0          # the hero looks along -x: its right is +y


def test_hard_sun_cards_scale_with_the_subject_and_rim_is_optional():
    p = _p("sports_car")
    cards = R.hard_sun_cards(p, _hero(p), {"fillRatio": 0.3, "rim": 0.4})
    assert [c.name for c in cards] == ["valora_sun_fill", "valora_sun_rim"]
    assert cards[0].power == 0.3 and cards[0].sizeX == pytest.approx(1.5 * p.radius)
    assert len(R.hard_sun_cards(p, _hero(p), {"fillRatio": 0.3, "rim": 0.0})) == 1


def test_neon_hues_split_around_the_world_hue():
    assert R.neon_hues(285.0, 150.0) == (210.0, 0.0)
    assert R.neon_hues(10.0, 60.0) == (340.0, 40.0)


def test_rim_neon_rims_sit_behind_either_side():
    p = _p("sports_car")
    a, b, fill = R.rim_neon_layout(p, _hero(p), {"rimStrength": 1.4, "hueSplit": 150.0, "keyAzimuthDeg": 140.0})
    cx, cy, _ = p.center
    assert a.center[0] < cx and b.center[0] < cx                 # behind (the hero is at +x)
    assert (a.center[1] - cy) * (b.center[1] - cy) < 0           # one each side
    assert fill.power < a.power


def test_neg_fill_card_off_at_zero():
    p = _p("sports_car")
    assert R.neg_fill_card(p, _hero(p), 0.0) is None
    c = R.neg_fill_card(p, _hero(p), 0.3)
    assert c.role == "negfill" and c.sizeX == pytest.approx(0.6 * p.radius)
