import pytest

from engine.physics import contact, tyre


def test_sink_depends_on_ground_type_and_never_swallows_a_small_subject():
    assert contact.sink_m("studio", 1.4) == 0.0 and contact.sink_m("asphalt", 1.4) == 0.0
    assert contact.sink_m("grass", 1.4) == pytest.approx(0.012)
    assert contact.sink_m("snow", 0.05) == pytest.approx(0.005)   # capped at 10% of a 5 cm subject
    with pytest.raises(KeyError):
        contact.sink_m("lava", 1.0)


def test_ao_distance_scales_with_height():
    assert contact.ao_distance(1.4) == pytest.approx(0.07) and contact.ao_distance(0.0) > 0


def test_grounded_window():
    assert contact.grounded(0.0, 0.0) and contact.grounded(-0.012, 0.012)
    assert not contact.grounded(0.004, 0.0)            # a 4 mm gap: floating
    assert not contact.grounded(-0.02, 0.012)          # sunk deeper than the ground allows


def test_deflection_from_patch_length_is_chord_geometry():
    d = tyre.deflection(0.33, 0.45)                     # METHODS CD-02: r 0.33 m -> d 5-12 mm
    assert d == pytest.approx(0.45 ** 2 * 0.33 / 8) and 0.005 <= d <= 0.012
    assert tyre.patch_length(0.33, d) == pytest.approx(0.45 * 0.33, rel=0.02)


def test_deform_clamps_to_the_ground_and_bulges_the_sidewall():
    r, d, hw = 0.35, tyre.deflection(0.35, 0.45), 0.14
    z, ax = tyre.deform(-0.004, 0.14, ground=0.0, d=d, radius=r, half_width=hw, bulge_frac=0.25)
    assert z == 0.0 and ax == pytest.approx(0.14 + 0.25 * d)          # full bulge at the patch, outer wall
    z, ax = tyre.deform(-0.004, -0.14, ground=0.0, d=d, radius=r, half_width=hw, bulge_frac=0.25)
    assert ax == pytest.approx(-0.14 - 0.25 * d)                       # inner wall bulges inward
    assert tyre.deform(0.3 * r, 0.14, 0.0, d, r, hw, 0.25) == (0.3 * r, 0.14)   # no bulge 0.3 r up
    z, ax = tyre.deform(0.0, 0.0, 0.0, d, r, hw, 0.25)
    assert (z, ax) == (0.0, 0.0)                                       # the tread centre does not move sideways
