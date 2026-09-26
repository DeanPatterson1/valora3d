import pytest

from engine.physics import contact, tyre


def test_sink_depends_on_ground_type_and_never_swallows_a_small_subject():
    assert contact.sink_m("studio", 1.4) == 0.0 and contact.sink_m("asphalt", 1.4) == 0.0
    assert contact.sink_m("grass", 1.4) == pytest.approx(0.020)   # round 6: a parked car sits into turf and soil
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


def test_a_small_subject_gets_a_tighter_gap_tolerance():
    # review fix 16 (low): 1 mm is a visible gap under a 5 cm subject; min(1 mm, 0.5% of its height)
    assert contact.gap_tol(0.05) == pytest.approx(0.00025) and contact.gap_tol(1.3) == contact.GROUND_TOL_M
    from engine.physics import probes
    assert probes.grounded_ok({"minZ": 0.0006}, 0.0) and not probes.grounded_ok({"minZ": 0.0006}, 0.0, height=0.05)


def test_degenerate_inputs_do_not_crash():
    # review fix 14 (low)
    from engine.physics import settle
    assert tyre.deflection(0.0, 0.45) == 0.0
    sz = settle.squash_z(0.0, 0.0, 0.3)
    assert sz > 0.0 and settle.squash_xy(sz) > 0.0


def test_a_vehicle_seam_reaches_under_its_sills():
    # review fix 7: 5% of a 1.3 m car is 65 mm, less than its ride height; the seam must reach the sills
    assert contact.contact_reach(1.3, ride_height=0.071) == pytest.approx(1.5 * 0.071)
    assert contact.contact_reach(1.3, ride_height=0.2) == pytest.approx(0.3)
    assert contact.contact_reach(0.03) == contact.ao_distance(0.03)


def test_a_tyre_modelled_already_flat_is_left_alone():
    # review fix 18 (low): a pre-flattened tyre already shows its patch; a second one would double it
    assert tyre.preflattened(0.15, 0.35, 0.45) and not tyre.preflattened(0.02, 0.35, 0.45)


def test_a_wheel_modelled_a_little_off_the_ground_drops_onto_it():
    # sports_car (measured 2026-09-25): its rear tyres sit 15 mm above z = 0 in the source model
    assert tyre.wheel_drop(0.015, 0.369) == pytest.approx(0.015)
    assert tyre.wheel_drop(-0.001, 0.35) == 0.0                   # already touching
    assert tyre.wheel_drop(0.2, 0.35) == 0.0                      # a lifted wheel (a jack, a wheelie) stays


def test_soft_deform_flattens_the_footprint_and_bulges_around_it():
    z, rho = contact.soft_deform(-0.01, 0.05, ground=0.0, dip=0.018, height=0.3, bulge_frac=0.2)
    assert z == 0.0 and rho == pytest.approx(0.05 + 0.2 * 0.018)
    assert contact.soft_deform(0.2, 0.05, 0.0, 0.018, 0.3, 0.2) == (0.2, 0.05)   # above the falloff: untouched


def test_a_soft_dip_needs_soft_contact_and_is_small_on_a_hard_floor():
    # review fix 6: the sneaker's hard sole flattened 9 mm into a studio floor
    assert contact.soft_dip_m(0.06, 0.3, "grass", 1.0) == pytest.approx(0.018)        # soft cover: full dip
    assert contact.soft_dip_m(0.06, 0.3, "studio", 1.0) == contact.HARD_DIP_MAX_M      # hard floor: capped
    assert contact.soft_dip_m(0.02, 0.1, "studio", 1.0) == pytest.approx(0.002)       # under the cap
    assert contact.soft_dip_m(0.06, 0.3, "grass", 0.3) == 0.0                          # a hard sole touches
    assert contact.HARD_DIP_MAX_M <= 0.005


def _car(rear_up=0.0, one_up=0.0):
    ws = [{"center": [x, y, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0]}
          for y in (1.2, -1.25) for x in (0.8, -0.8)]
    bottoms = [one_up, 0.0, rear_up, rear_up]
    return ws, bottoms


def test_a_floating_axle_tilts_the_car_about_the_grounded_axle():
    # review fix 4: sports_car's rear axle is modelled 15 mm up; the whole car turns about the front axle's
    # contact line instead of the rear wheels dropping 15 mm out of their arches
    import math
    ws, bottoms = _car(rear_up=0.015)
    bottoms[3] += 3e-8                                                      # float noise on one rear (sports_car)
    plan = tyre.axle_plan(ws, bottoms, [0.0, 1.0, 0.0])
    assert plan["drops"] == [0.0, 0.0, 0.0, 0.0]
    tilt = plan["tilt"]
    assert tilt["angle"] == pytest.approx(math.asin(0.015 / 2.45))
    rear_bottom = tyre.tilt_point((0.8, -1.25, 0.015), tilt)
    assert rear_bottom[2] == pytest.approx(0.0, abs=1e-4)                  # the rear tyre comes down
    assert tyre.tilt_point((0.8, 1.2, 0.0), tilt) == pytest.approx((0.8, 1.2, 0.0))   # the front stays


def test_a_single_floating_wheel_drops_alone_and_the_drop_is_capped():
    ws, bottoms = _car(one_up=0.008)
    plan = tyre.axle_plan(ws, bottoms, [0.0, 1.0, 0.0])
    assert plan["tilt"] is None and plan["drops"] == pytest.approx([0.008, 0.0, 0.0, 0.0])
    ws, bottoms = _car(one_up=0.03)                                        # <= 0.1 r: a modelling offset
    assert tyre.axle_plan(ws, bottoms, [0.0, 1.0, 0.0])["drops"][0] == pytest.approx(min(0.02, 0.05 * 0.35))
    assert tyre.axle_plan(*_car(), [0.0, 1.0, 0.0]) == {"tilt": None, "drops": [0.0] * 4, "rigidDrop": 0.0}


def test_a_wholly_floating_vehicle_drops_rigidly_first():
    # review item 8: every wheel up (any axle count) is one rigid drop by the smallest shared lift, then
    # the usual tilt / lone-wheel rules on what is left
    import math
    ws, _ = _car()
    plan = tyre.axle_plan(ws, [0.01] * 4, [0.0, 1.0, 0.0])
    assert plan == {"tilt": None, "drops": [0.0] * 4, "rigidDrop": pytest.approx(0.01)}
    plan = tyre.axle_plan(ws, [0.005, 0.005, 0.015, 0.015], [0.0, 1.0, 0.0])
    assert plan["rigidDrop"] == pytest.approx(0.005) and plan["drops"] == [0.0] * 4
    assert plan["tilt"]["angle"] == pytest.approx(math.asin(0.01 / 2.45))
    six = [{"center": [x, y, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0]}
           for y in (2.0, 0.0, -2.0) for x in (0.8, -0.8)]
    plan = tyre.axle_plan(six, [0.008, 0.008, 0.012, 0.008, 0.008, 0.008], [0.0, 1.0, 0.0])
    assert plan["rigidDrop"] == pytest.approx(0.008) and plan["tilt"] is None
    assert plan["drops"] == pytest.approx([0.0, 0.0, 0.004, 0.0, 0.0, 0.0])


def test_the_underside_grid_fills_holes_and_grows_past_the_silhouette():
    # review item 3: ground_conform presses grass under the subject's underside heightfield; a see-through
    # gap inside the silhouette (a toy's open wheel well) must not let a blade stand up through the subject
    import numpy as np
    nan = np.nan
    z = np.array([[nan, nan, nan, nan, nan, nan],
                  [nan, 0.3, 0.2, 0.2, 0.3, nan],
                  [nan, 0.2, nan, nan, 0.1, nan],
                  [nan, 0.3, 0.2, 0.2, 0.3, nan],
                  [nan, nan, nan, nan, nan, nan]])
    f = contact.underside_fill(z, 0)
    assert f[2, 2] == 0.2 and f[2, 3] == 0.1                       # holes take their lowest neighbour
    assert np.isnan(f[0]).all() and np.isnan(f[:, 0]).all()        # outside the silhouette stays open
    g = contact.underside_fill(z, 1)
    assert not np.isnan(g).any() and g[0, 0] == 0.3 and g[2, 5] == 0.1   # one ring of growth, lowest neighbour
    assert np.isnan(contact.underside_fill(np.full((3, 3), nan), 2)).all()


def test_the_underside_grid_never_rises_above_a_step_between_samples():
    # a linear surface between a high and a low sample overshoots the true step: each sample takes the
    # lowest of itself and its neighbours (review item 3; toycar at frame 30 poked 1.9 mm through)
    import numpy as np
    nan = np.nan
    z = np.array([[0.1, 0.1, 0.5, 0.5], [0.1, 0.1, 0.5, 0.5], [nan, 0.1, 0.5, nan]])
    f = contact.underside_floor(z)
    assert f[0, 2] == 0.1 and f[0, 3] == 0.5 and f[1, 3] == 0.5 and np.isnan(f[2, 0]) and np.isnan(f[2, 3])
