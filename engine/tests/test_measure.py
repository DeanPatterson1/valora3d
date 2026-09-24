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
