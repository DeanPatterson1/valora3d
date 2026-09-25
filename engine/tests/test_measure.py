import math

import pytest

from engine.ingest.measure import Sample, vehicle_facts, wheel_extras
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
    body = [Sample((x / 10, y / 10, 0.2 + z / 10), (0, 0, -1), 1e-4, "glossy", True, False, 0.0, obj=0, island=0)
            for x in range(-6, 7) for y in range(-19, 20) for z in (0, 9)]
    v = vehicle_facts(ws, body, [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])
    assert v["forwardAxis"] == [0.0, 1.0, 0.0] and v["wheelbaseM"] == pytest.approx(2.6)
    assert v["trackM"] == pytest.approx(1.6) and v["rideHeightM"] == pytest.approx(0.2, abs=0.01)
    assert v["bodySeparable"] is True and v["vehicleClass"] == "sport"
