"""Phase 5 Task 54: manifest keys for worlds, effects, motions and cameras."""
import copy
import json

import pytest

from engine.catalog import Catalog, CatalogError, _check_manifest

WORLD = {"id": "w", "kind": "world", "description": "d",
         "params": {"timeOfDay": {"type": "enum", "values": ["dusk", "night"], "default": "night"}},
         "subjectSizeM": [0.02, 8.0],
         "aspects": ["9:16"], "costWeight": 1.0, "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T3",
         "hasGround": True, "groundType": "asphalt", "hasFoliage": False, "windDefault": 0.8,
         "outdoor": True, "weathers": ["dry", "wet", "rain", "fog"], "temperature": "mild",
         "timeOfDay": {"param": "timeOfDay", "values": ["dusk", "night"]}, "toneParam": None, "driveLaneM": 24.0}
FX = {"id": "rain", "kind": "effect", "description": "d", "params": {"rateMmH": {"type": "number", "min": 0.5, "max": 50, "default": 4}},
      "subjectSizeM": [0.02, 30.0], "aspects": ["9:16"], "costWeight": 1.6, "tags": {"mood": [], "energy": [], "palette": []},
      "tierMax": "T3", "maxPerClip": 1,
      "physics": {"taxonomy": ["FL-01"], "state": "stateless", "windDriven": True, "couplings": ["wet_surface"],
                  "excludes": ["snow"], "requiresWorld": {"outdoor": True, "hasGround": True},
                  "timeScaleParam": None, "windCalibration": {"unit": "slant", "perMs": 1.0}}}
CAM = {"id": "c", "kind": "camera", "description": "d", "framing": "full",
       "params": {"distance": {"type": "number", "min": 1, "max": 3, "default": 2},
                  "lensMm": {"type": "number", "min": 20, "max": 90, "default": 50},
                  "fstop": {"type": "number", "min": 1.4, "max": 16, "default": 4}},
       "subjectSizeM": [0.02, 8.0], "aspects": ["9:16"], "costWeight": 1.0,
       "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T3"}


def test_valid_phase5_world_and_effect_manifests_load():
    _check_manifest("world", "w", copy.deepcopy(WORLD))
    _check_manifest("effect", "rain", copy.deepcopy(FX))
    _check_manifest("camera", "c", {**copy.deepcopy(CAM), "follows": "subject", "hookable": False,
                                    "requiresMotion": ["translates"]})


@pytest.mark.parametrize("key,bad", [("weathers", ["dry", "hail"]), ("weathers", ["rain"]), ("temperature", "warmish"),
                                     ("outdoor", "yes"), ("driveLaneM", -1), ("timeOfDay", {"param": "x"}),
                                     ("timeOfDay", {"param": "timeOfDay", "values": ["noon"]}), ("toneParam", "tone")])
def test_bad_world_keys_are_rejected(key, bad):
    with pytest.raises(CatalogError):
        _check_manifest("world", "w", {**copy.deepcopy(WORLD), key: bad})


@pytest.mark.parametrize("key,bad", [("couplings", "wet_surface"), ("excludes", [3]), ("requiresWorld", {"colour": 1}),
                                     ("requiresWorld", {"outdoor": "yes"}), ("windCalibration", {"unit": "slant"}),
                                     ("timeScaleParam", 3)])
def test_bad_effect_physics_keys_are_rejected(key, bad):
    m = copy.deepcopy(FX)
    m["physics"][key] = bad
    with pytest.raises(CatalogError):
        _check_manifest("effect", "rain", m)


def test_max_per_clip_and_camera_follows():
    for bad in (0, 1.5, True):
        with pytest.raises(CatalogError):
            _check_manifest("effect", "rain", {**copy.deepcopy(FX), "maxPerClip": bad})
    with pytest.raises(CatalogError):
        _check_manifest("camera", "c", {**copy.deepcopy(CAM), "follows": "orbit"})


@pytest.mark.parametrize("key,bad", [("hookable", "no"), ("requiresMotion", "translates"), ("requiresMotion", ["flies"])])
def test_bad_camera_hookable_and_requires_motion_are_rejected(key, bad):
    with pytest.raises(CatalogError):
        _check_manifest("camera", "c", {**copy.deepcopy(CAM), key: bad})


def _write(root, kind, bid, manifest, files=None):
    d = root / kind / bid
    d.mkdir(parents=True)
    (d / "block.json").write_text(json.dumps(manifest))
    for name, text in (files or {}).items():
        (d / name).write_text(text)


def test_post_load_couplings_and_excludes_must_name_real_effects(tmp_path):
    _write(tmp_path, "effect", "rain", copy.deepcopy(FX))
    with pytest.raises(CatalogError, match="wet_surface"):
        Catalog.load(tmp_path)
    _write(tmp_path, "effect", "wet_surface", {**copy.deepcopy(FX), "id": "wet_surface",
                                                 "physics": {"taxonomy": [], "state": "stateless"}})
    with pytest.raises(CatalogError, match="snow"):
        Catalog.load(tmp_path)
    _write(tmp_path, "effect", "snow", {**copy.deepcopy(FX), "id": "snow", "physics": {}})
    assert Catalog.load(tmp_path).get("effect", "rain")["maxPerClip"] == 1


def test_time_scale_param_must_name_an_own_param(tmp_path):
    m = copy.deepcopy(FX)
    m["physics"].update(couplings=[], excludes=[], timeScaleParam="speed")
    _write(tmp_path, "effect", "rain", m)
    with pytest.raises(CatalogError, match="timeScaleParam"):
        Catalog.load(tmp_path)


def test_catalog_couplings_resolve_to_real_blocks():
    cat = Catalog.load()
    for bid in cat.ids("effect"):
        for c in (cat.get("effect", bid).get("physics") or {}).get("couplings", []):
            assert cat.get("effect", c) is not None, (bid, c)


def test_studio_is_indoor_and_dry_only():
    m = Catalog.load().get("world", "studio_cyc")
    assert m["outdoor"] is False and m["weathers"] == ["dry"] and m["toneParam"] == "tone"
    assert m["temperature"] == "mild" and m["driveLaneM"] == 0.0


MOTION = {"id": "glide", "kind": "motion", "description": "d", "params": {},
          "subjectSizeM": [0.02, 8.0], "aspects": ["9:16"], "costWeight": 1.0,
          "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T3"}


def test_motion_path_loader(tmp_path):
    _write(tmp_path, "motion", "glide", {**MOTION},
           {"path.py": "def sample(params, profile, t, duration):\n    return t\n\n"
                       "def flags(params):\n    return {'translates': True}\n"})
    _write(tmp_path, "motion", "still", {**MOTION, "id": "still"})
    _write(tmp_path, "motion", "noflags", {**MOTION, "id": "noflags"},
           {"path.py": "def sample(params, profile, t, duration):\n    return 0\n"})
    cat = Catalog.load(tmp_path)
    assert cat.has_motion_path("glide") and not cat.has_motion_path("still")
    assert not cat.has_motion_path("nope") and not cat.has_motion_path("../x")
    assert cat.load_motion_path("glide")({}, None, 2.5, 10.0) == 2.5
    assert cat.load_motion_flags("glide")({}) == {"translates": True}
    assert cat.load_motion_flags("noflags") is None
    with pytest.raises(CatalogError):
        cat.load_motion_path("still")


def test_motion_flags_come_from_the_asking_catalog(tmp_path):
    """Review chunk1 #7: two catalog roots with the same motion id keep their own flags() and still(), even
    when their loads interleave (sys.modules holds one module per name)."""
    for root, v in ((tmp_path / "a", "A"), (tmp_path / "b", "B")):
        _write(root, "motion", "glide", {**MOTION},
               {"path.py": "def sample(params, profile, t, duration):\n    return t\n\n"
                           f"def flags(params):\n    return {{'from': '{v}'}}\n\n"
                           f"def still(params):\n    return {v == 'A'}\n"})
    a = Catalog.load(tmp_path / "a")
    a.load_motion_path("glide")
    b = Catalog.load(tmp_path / "b")
    b.load_motion_path("glide")
    assert a.load_motion_flags("glide")({}) == {"from": "A"} and b.load_motion_flags("glide")({}) == {"from": "B"}
    assert a.motion_still("glide", {}) is True and b.motion_still("glide", {}) is False
