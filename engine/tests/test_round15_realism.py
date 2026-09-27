"""Round 15 realism layers, pure: the meadow floor's new species in their own patches (field_layout.field_cover), the
leaves at a parked car's tyres (courtyard_layout.tyre_litter), the rain's capture layer (grade_plan CAPTURE wet)
and the pinned CC0 assets the field now needs."""
import math


def _prof():
    from harness import realism_round as rr
    return rr.load_profile()


def test_the_meadow_floor_grows_each_species_in_its_own_patches_and_denser_round_the_camera():
    from engine.worlds import field_layout as FL
    prof = _prof()
    cam = (prof.center[0] - 2.4, prof.center[1] - 1.4, 0.8)
    cov = FL.field_cover(prof, 7, 11.4, [], 1.0, cameras=[cam])
    assert set(cov) == set(FL.COVER_KINDS)
    lo, hi = prof.boundsMin, prof.boundsMax
    for kind, pts in cov.items():
        assert pts, kind
        for x, y, yaw, s in pts:                 # never deep under the body
            deep = lo[0] + 0.35 < x < hi[0] - 0.35 and lo[1] + 0.35 < y < hi[1] - 0.35
            assert not deep
    bare = FL.field_cover(prof, 7, 11.4, [], 1.0, cameras=[])     # the same field with no camera to crowd round
    for kind, pts in cov.items():
        def near(ps):
            return sum(1 for x, y, *_ in ps if math.hypot(x - cam[0], y - cam[1]) < FL.COVER_FORE_M)
        assert near(pts) > 1.2 * near(bare[kind]), kind              # denser round the camera, same patches
    # patches, not an even sprinkle: the mask is 0 somewhere and 1 somewhere for every kind
    for kind in FL.COVER_KINDS:
        vals = [FL.cover_mask(x * 0.37, y * 0.41, 7, kind) for x in range(-20, 20) for y in range(-20, 20)]
        assert min(vals) == 0.0 and max(vals) > 0.99
    # and the kinds do not share one patch map
    a = [FL.cover_mask(x * 0.5, 0.0, 7, "clover") for x in range(200)]
    b = [FL.cover_mask(x * 0.5, 0.0, 7, "moss") for x in range(200)]
    assert a != b


def test_the_field_layout_carries_the_floor_species_with_the_weeds():
    from engine.worlds import field_layout as FL
    prof = _prof()
    lay = FL.layout(prof, 7, 0.45, "grass", False, cameras=[(prof.center[0] - 2.4, prof.center[1] - 1.4, 0.8)])
    assert set(FL.COVER_KINDS) <= set(lay["flora"]) and {"weeds", "flowers"} <= set(lay["flora"])


def test_leaves_lie_at_every_tyres_foot_on_its_outer_side():
    from engine.worlds.courtyard_layout import TYRE_LITTER, tyre_litter
    prof = _prof()
    leaves = tyre_litter(prof, 7)
    wheels = [w for w in prof.wheels if w.get("contact")]
    lo, hi = TYRE_LITTER["perTyre"]
    assert lo * len(wheels) <= len(leaves) <= hi * len(wheels)
    for lf in leaves:
        d = min(math.hypot(lf["xy"][0] - w["contact"][0], lf["xy"][1] - w["contact"][1]) for w in wheels)
        assert d < 1.5 * max(w["radius"] for w in wheels) + TYRE_LITTER["reachM"][1]
    assert tyre_litter(prof, 7) == leaves


def test_the_rain_by_day_gets_the_wet_capture_layer():
    from engine.grade_plan import CAPTURE, with_capture
    wet = with_capture({}, {"world": {"id": "rain_courtyard", "params": {"wetness": 0.8, "timeOfDay": "overcast_day"}}})
    assert wet["capture"] is CAPTURE["wet"]
    c = CAPTURE["wet"]
    assert c["glow"]["strength"] > CAPTURE["day"]["glow"]["strength"] and c["glow"]["size"] > CAPTURE["day"]["glow"]["size"]
    assert c["veil"]["threshold"] == 0.0 and 0 < c["veil"]["strength"] < 0.15      # a faint veil over everything
    night = with_capture({}, {"world": {"id": "night_street", "params": {"wetness": 1.0, "timeOfDay": "night"}}})
    assert night["capture"] is CAPTURE["night"]                                     # night stays night


def test_the_field_needs_its_new_cc0_species_pinned():
    from engine.assets import load_manifest
    from engine.world_assets import required
    files, gltfs = required("golden_field", {"timeOfDay": "golden"}, "final")
    man = load_manifest()["assets"]
    for slug in ("grass_bermuda_01", "shrub_sorrel_01", "moss_01", "nettle_plant"):
        aid = f"{slug}_1k"
        assert aid in gltfs and f"{slug}_Alpha_1k" in files and f"{slug}_Alpha_1k" in man   # cards cut out
        a = man[aid]
        assert a["licence"] == "CC0-1.0" and a["source"].startswith("https://polyhaven.com/a/")
        assert a["licenceProof"] == "https://polyhaven.com/license" and len(a["sha256"]) == 64
