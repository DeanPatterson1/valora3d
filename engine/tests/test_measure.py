import math

import pytest

from engine.ingest.measure import Sample, dangling_parts, ground_contacts, soft_parts, vehicle_facts, wheel_extras
from engine.ingest.measure import infer_units, size_class, material_class, build_profile


def test_units():
    assert infer_units(4.5) == ("m", 1.0, "high")
    assert infer_units(300.0) == ("mm", 0.001, "low")      # 30 cm shoe authored in mm
    assert infer_units(4500.0) == ("mm", 0.001, "low")     # car in mm
    assert infer_units(0.001) == ("unknown", 1.0, "low")


def test_units_ambiguous_ranges_are_low_confidence():
    # 0.02-0.1 m reads equally well as a 2-10 m object authored in cm (x100)
    for v in (0.02, 0.05, 0.1):
        assert infer_units(v) == ("m", 1.0, "low"), v
    # above 10 m is plausible metres but rare for a product shot; flag it
    for v in (10.5, 30.0):
        assert infer_units(v) == ("m", 1.0, "low"), v
    for v in (0.11, 0.3, 4.5, 10.0):
        assert infer_units(v) == ("m", 1.0, "high"), v


def test_size_class():
    assert [size_class(v) for v in (0.05, 0.3, 1.2, 4.5, 20)] == \
        ["macro", "hand", "furniture", "vehicle", "architectural"]


def test_material_class_priority():
    assert material_class({"emission": 1, "transmission": 1}) == "emissive"
    assert material_class({"metallic": 1, "roughness": 0.1}) == "metal"
    assert material_class({"roughness": 0.1}) == "glossy"
    assert material_class({"roughness": 0.9}) == "fabric"
    assert material_class({"roughness": 0.5}) == "matte"


def test_build_profile_rescales_recentres_and_grounds():
    raw = {"boundsMin": [1000, -950, 200], "boundsMax": [5500, 950, 1500], "polyCount": 5,
           "rigged": False, "animated": False,
           "materials": [{"area": 3.0, "metallic": 1.0, "roughness": 0.2, "transmission": 0, "emission": 0, "subsurface": 0},
                         {"area": 1.0, "metallic": 0.0, "roughness": 0.05, "transmission": 1.0, "emission": 0, "subsurface": 0}]}
    p = build_profile(raw)
    assert p.unitGuess == "mm" and p.scaleConfidence == "low"
    assert [round(v, 3) for v in p.sizeM] == [4.5, 1.9, 1.3]
    assert [round(v, 3) for v in p.boundsMin] == [-2.25, -0.95, 0.0]
    assert p.sizeClass == "vehicle" and p.categoryHint == "vehicle-like"
    assert p.materials == [{"class": "metal", "share": 0.75}, {"class": "glass", "share": 0.25}]


def test_build_profile_keeps_placement_transform():
    raw = {"boundsMin": [1000, -950, 200], "boundsMax": [5500, 950, 1500], "polyCount": 5}
    p = build_profile(raw)
    assert p.sourceCenter == [3250.0, 0.0, 850.0]
    assert p.sourceMinZ == 200 and p.scaleFactor == 0.001
    # placed = ((x - cx, y - cy, z - minZ)) * scaleFactor must land exactly on the placed bounds
    def place(v):
        return [(v[0] - p.sourceCenter[0]) * p.scaleFactor, (v[1] - p.sourceCenter[1]) * p.scaleFactor,
                (v[2] - p.sourceMinZ) * p.scaleFactor]
    for got, want in ((place(raw["boundsMin"]), p.boundsMin), (place(raw["boundsMax"]), p.boundsMax)):
        assert all(abs(a - b) < 1e-9 for a, b in zip(got, want)), (got, want)



def _torus(c, R, tube, cls, obj, island, n=240, gloss=False):
    """Samples on a tyre-like torus whose axle is x (placed coords)."""
    out = []
    for i in range(n):
        u, v = 2 * math.pi * i / n, 2 * math.pi * ((i * 7) % n) / n
        rho = R + tube * math.cos(v)
        p = (c[0] + tube * math.sin(v), c[1] + rho * math.cos(u), c[2] + rho * math.sin(u))
        nrm = (math.sin(v), math.cos(v) * math.cos(u), math.cos(v) * math.sin(u))
        out.append(Sample(p, nrm, 1e-4, cls, gloss, False, 0.0, obj=obj, island=island))
    return out


def test_wheel_extras_measure_width_tyre_band_contact_and_separability():
    w = {"center": [0.8, 1.3, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "confidence": "high"}
    samples = _torus(w["center"], 0.28, 0.07, "fabric", 1, 0)
    islands = [{"key": (1, 0), "n": 1024, "lo": [0.73, 0.95, 0.0], "hi": [0.87, 1.65, 0.70], "centroid": [0.8, 1.3, 0.35]}]
    bmin, bmax = [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1]
    wheel_extras([w], samples, islands, bmin, bmax)
    assert 0.09 <= w["width"] <= 0.14
    assert 0.55 <= w["tyreBand"][0] <= 0.66 and w["tyreBand"][1] == 1.0
    assert w["contact"] == [0.8, 1.3, 0.0] and w["separable"] is True


def test_a_wheel_welded_into_the_body_is_not_separable():
    w = {"center": [0.8, 1.3, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "confidence": "high"}
    body = [{"key": (0, 0), "n": 9000, "lo": [-0.9, -2.0, 0.0], "hi": [0.9, 2.0, 1.1], "centroid": [0, 0, 0.6]}]
    wheel_extras([w], _torus(w["center"], 0.28, 0.07, "fabric", 0, 0), body, [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])
    assert w["separable"] is False


def test_vehicle_facts_classify_a_low_separable_car_as_sport():
    ws = [{"center": [x, y, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "separable": True, "width": 0.14,
           "tyreBand": [0.6, 1.0]} for x in (-0.8, 0.8) for y in (-1.3, 1.3)]
    body = [Sample((x / 10, y / 10, 0.1 + z / 10), (0, 0, -1), 1e-4, "glossy", True, False, 0.0, obj=0, island=0)
            for x in range(-6, 7) for y in range(-19, 20) for z in (0, 9)]
    v = vehicle_facts(ws, body, [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])
    assert v["forwardAxis"] == [0.0, 1.0, 0.0] and v["wheelbaseM"] == pytest.approx(2.6)
    assert v["trackM"] == pytest.approx(1.6) and v["rideHeightM"] == pytest.approx(0.1, abs=0.01)
    assert v["bodySeparable"] is True and v["vehicleClass"] == "sport"


def test_a_sedan_riding_at_0_4_r_is_comfort_not_sport():
    # review fix 9: a low roofline alone read sedans as sport; ride height / wheel radius separates them
    ws = [{"center": [x, y, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "separable": True, "width": 0.2,
           "tyreBand": [0.6, 1.0]} for x in (-0.8, 0.8) for y in (-1.3, 1.3)]
    body = [Sample((x / 10, y / 10, 0.14 + z / 10), (0, 0, -1), 1e-4, "glossy", True, False, 0.0, obj=0, island=0)
            for x in range(-6, 7) for y in range(-19, 20) for z in (0, 9)]
    assert vehicle_facts(ws, body, [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])["vehicleClass"] == "comfort"


def _s(p, cls="matte", obj=0, island=0):
    return Sample(tuple(p), (0.0, 0.0, 1.0), 1e-4, cls, False, False, 0.0, obj=obj, island=island)


def test_ground_contacts_are_the_patches_at_z0():
    feet = [_s((x / 100 + dx, y / 100 + dy, 0.0)) for dx, dy in ((-0.4, -0.4), (0.4, -0.4), (0.4, 0.4), (-0.4, 0.4))
            for x in range(3) for y in range(3)]
    top = [_s((0, 0, 0.5))] * 20
    got = ground_contacts(feet + top, [-0.5, -0.5, 0.0], [0.5, 0.5, 0.8])
    assert len(got) == 4 and all(g["center"][2] == 0.0 for g in got)
    assert sum(g["share"] for g in got) == pytest.approx(1.0)


def test_roughness_alone_is_only_a_low_confidence_soft_part():
    # review fix 3: stone, wood, concrete and cardboard are rough non-metals too
    ss = [_s((0, 0, z / 100), "fabric", obj=0) for z in range(30)]
    got = soft_parts(ss, {0: 0}, "hand", has_wheels=False, rigged=False, H=0.3)
    assert [s["confidence"] for s in got] == ["low"]


def test_soft_parts_high_only_for_small_unrigged_wheel_less_fabric():
    ss = [_s((0, 0, z / 100), "fabric", obj=0)._replace(soft_cue=True) for z in range(30)]
    parts = {0: 0}
    hi = soft_parts(ss, parts, "hand", has_wheels=False, rigged=False, H=0.3)
    assert hi == [{"part": 0, "share": 1.0, "touchesGround": True, "confidence": "high"}]
    assert soft_parts(ss, parts, "vehicle", has_wheels=True, rigged=False, H=0.3)[0]["confidence"] == "low"
    assert soft_parts(ss, parts, "furniture", has_wheels=False, rigged=True, H=0.3)[0]["confidence"] == "low"
    assert soft_parts([_s((0, 0, z / 100), "metal") for z in range(30)], parts, "hand", False, False, 0.3) == []


def test_a_strap_hanging_from_one_end_is_dangling():
    box = [_s((x / 100, y / 100, 0.30 + z / 100), obj=0, island=0) for x in range(0, 11) for y in range(-5, 6) for z in range(0, 13)]
    strap = [_s((0.104, 0.0, 0.27 + z / 1000), "fabric", obj=1, island=0) for z in range(0, 151, 5)]
    isl = [{"key": (1, 0), "n": 24, "lo": [0.102, -0.006, 0.27], "hi": [0.106, 0.006, 0.42], "centroid": [0.104, 0, 0.345]},
           {"key": (0, 0), "n": 8, "lo": [0.0, -0.05, 0.30], "hi": [0.10, 0.05, 0.42], "centroid": [0.05, 0, 0.36]}]
    got = dangling_parts(box + strap, isl, longest=0.42, H=0.42)
    assert len(got) == 1 and got[0]["confidence"] == "high"
    assert got[0]["pivot"][2] > got[0]["tip"][2] and got[0]["lengthM"] == pytest.approx(0.15, abs=0.01)


def test_a_rail_attached_at_both_ends_or_lying_on_the_ground_is_not_high():
    rail = [_s((0.0, y / 100, 0.001), obj=1) for y in range(0, 31)]
    ends = [_s((0.0, -0.005, 0.001), obj=0), _s((0.0, 0.305, 0.001), obj=2)]
    isl = [{"key": (1, 0), "n": 31, "lo": [-0.002, 0.0, 0.0], "hi": [0.002, 0.30, 0.002], "centroid": [0, 0.15, 0.001]}]
    assert all(d["confidence"] != "high" for d in dangling_parts(rail + ends, isl, longest=0.4, H=0.3))


def test_wheel_extras_snap_a_noisy_contact_centre_onto_the_round_tyre_island():
    # wheels() centres a wheel on its random contact-patch samples (~2 cm noise on a 0.35 m tyre);
    # a round island's centroid sits on the true axle, so the spin test would miss by that noise.
    w = {"center": [0.805, 1.2825, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "confidence": "high"}
    samples = _torus([0.8, 1.3, 0.35], 0.28, 0.07, "fabric", 1, 0)
    tyre = {"key": (1, 0), "n": 1024, "lo": [0.73, 0.95, 0.0], "hi": [0.87, 1.65, 0.70], "centroid": [0.8, 1.3, 0.35]}
    caliper = {"key": (2, 0), "n": 24, "lo": [0.76, 1.38, 0.43], "hi": [0.84, 1.46, 0.51], "centroid": [0.8, 1.42, 0.47]}
    wheel_extras([w], samples, [caliper, tyre], [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])
    assert w["center"] == [0.8, 1.3, 0.35] and w["contact"] == [0.8, 1.3, 0.0] and w["separable"] is True


def test_a_hanging_metal_rod_is_rigid_not_dangling():
    # vintage_microscope (2026-09-25 regen): a 10 cm glossy metal rod fixed at its top read as a strap.
    box = [_s((x / 100, y / 100, 0.30 + z / 100), obj=0, island=0) for x in range(0, 11) for y in range(-5, 6) for z in range(0, 13)]
    rod = [_s((0.104, 0.0, 0.27 + z / 1000), "metal", obj=1, island=0) for z in range(0, 151, 5)]
    isl = [{"key": (1, 0), "n": 24, "lo": [0.102, -0.006, 0.27], "hi": [0.106, 0.006, 0.42], "centroid": [0.104, 0, 0.345]}]
    assert [d["confidence"] for d in dangling_parts(box + rod, isl, longest=0.42, H=0.42)] == ["low"]


def test_a_hanging_matte_painted_rod_is_rigid_not_dangling():
    # review fix 10: matte is painted plastic or metal as often as cloth; only fabric/skin sway
    box = [_s((x / 100, y / 100, 0.30 + z / 100), obj=0, island=0) for x in range(0, 11) for y in range(-5, 6) for z in range(0, 13)]
    rod = [_s((0.104, 0.0, 0.27 + z / 1000), "matte", obj=1, island=0) for z in range(0, 151, 5)]
    isl = [{"key": (1, 0), "n": 24, "lo": [0.102, -0.006, 0.27], "hi": [0.106, 0.006, 0.42], "centroid": [0.104, 0, 0.345]}]
    assert [d["confidence"] for d in dangling_parts(box + rod, isl, longest=0.42, H=0.42)] == ["low"]


def test_tyre_width_is_the_tread_island_extent_along_the_axle():
    # review fix 11: percentiles of rubber samples read a 335 mm tyre as ~250 mm (the shoulders curve
    # away and the sidewall faces carry few samples); the tread island's box spans the whole tyre.
    w = {"center": [0.8, 1.3, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "confidence": "high"}
    samples = [_s((0.8 + a / 100, 1.3 + 0.35 * math.cos(u / 20), 0.35 + 0.35 * math.sin(u / 20)), "fabric", 1, 0)
               for a in range(-12, 13) for u in range(126)]                    # the tread face carries the area
    islands = [{"key": (1, 0), "n": 1024, "lo": [0.6325, 0.95, 0.0], "hi": [0.9675, 1.65, 0.70],
                "centroid": [0.8, 1.3, 0.35]}]
    wheel_extras([w], samples, islands, [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])
    assert w["width"] == pytest.approx(0.335, abs=0.002) and w["separable"] is True


def test_tyre_band_ignores_rough_pieces_that_do_not_reach_the_tread():
    # sports_car (2026-09-25 regen): matte brake discs at 0.4-0.6 r pulled tyreBand[0] below 0.5.
    w = {"center": [0.8, 1.3, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "confidence": "high"}
    tyre = _torus(w["center"], 0.28, 0.07, "fabric", 1, 0)
    disc = [_s((0.8, 1.3 + 0.16 * math.cos(a / 10), 0.35 + 0.16 * math.sin(a / 10)), "matte", obj=2) for a in range(63)]
    islands = [{"key": (1, 0), "n": 1024, "lo": [0.73, 0.95, 0.0], "hi": [0.87, 1.65, 0.70], "centroid": [0.8, 1.3, 0.35]},
               {"key": (2, 0), "n": 200, "lo": [0.79, 1.14, 0.19], "hi": [0.81, 1.46, 0.51], "centroid": [0.8, 1.3, 0.35]}]
    wheel_extras([w], tyre + disc, islands, [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])
    assert 0.55 <= w["tyreBand"][0] <= 0.66


def test_clips_are_measured_and_names_sanitised():
    from engine.ingest.measure import _clips
    got = _clips([{"frameStart": 1.0, "frameEnd": 49.0, "fps": 24.0, "name": "Walk<script>\u202e", "keys": 12},
                  {"frameStart": 5.0, "frameEnd": 5.0, "fps": 24.0, "name": "empty", "keys": 1}])
    assert got == [{"index": 0, "frameStart": 1.0, "frameEnd": 49.0, "fps": 24.0, "durationS": 2.0,
                    "nameHint": "Walkscript", "seamless": None}]


def test_clips_drop_stubs_before_indexing_and_name_the_nameless():
    """A clip under MIN_CLIP_S (a 1-frame pose stub) is dropped BEFORE indices are given, the same filter
    play_clip applies in Blender (engine.clips.clip_kept), so index i is one action on both sides."""
    from engine.ingest.measure import _clips
    got = _clips([{"frameStart": 1.0, "frameEnd": 2.0, "fps": 24.0, "name": "Pose", "keys": 1},
                  {"frameStart": 1.0, "frameEnd": 25.0, "fps": 24.0, "name": "", "keys": 3, "seamless": False},
                  {"frameStart": 1.0, "frameEnd": 25.0, "fps": 24.0, "name": "<>", "keys": 3}])
    assert [(c["index"], c["nameHint"], c["seamless"]) for c in got] == [(0, "clip0", False), (1, "clip1", None)]


def test_build_profile_carries_clips():
    raw = {"boundsMin": [0, 0, 0], "boundsMax": [1, 1, 1],
           "clips": [{"frameStart": 1.0, "frameEnd": 25.0, "fps": 24.0, "name": "Idle", "keys": 3}]}
    assert build_profile(raw).animationClips[0]["durationS"] == 1.0
