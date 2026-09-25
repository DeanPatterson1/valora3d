import pytest

from engine.catalog import GROUND_TYPES, KINDS, Catalog, CatalogError
from engine.tests.test_catalog import _base, _write


def _realism(bid="r", **extra):
    m = _base(bid, kind="realism", alwaysOn=True, directorSelectable=False,
              appliesWhen={"placement": ["ground"]})
    m.update(extra)
    return m


def test_new_kinds_exist():
    assert {"realism", "field", "sim"} <= set(KINDS)
    assert "studio" in GROUND_TYPES and "grass" in GROUND_TYPES


def test_a_realism_block_loads(tmp_path):
    _write(tmp_path, "realism", "r", _realism(autoParams=["x"], params={
        "x": {"type": "number", "min": 0, "max": 1, "default": 0.5}}))
    assert Catalog.load(tmp_path).ids("realism") == ["r"]


@pytest.mark.parametrize("extra,match", [
    ({"alwaysOn": False}, "always on"),
    ({"directorSelectable": True}, "always on"),
    ({"appliesWhen": None}, "appliesWhen"),
    ({"appliesWhen": {"weather": ["rain"]}}, "appliesWhen"),
    ({"appliesWhen": {"profile": ["wings"]}}, "appliesWhen.profile"),
    ({"appliesWhen": {"motion": ["flies"]}}, "appliesWhen.motion"),
    ({"appliesWhen": {"world": {"groundType": ["lava"]}}}, "appliesWhen.world"),
    ({"appliesWhen": {"materials": {"glass": 1.5}}}, "appliesWhen.materials"),
    ({"appliesWhen": {"sizeM": [2.0, 1.0]}}, "appliesWhen.sizeM"),
    ({"autoParams": ["nope"]}, "autoParams"),
    ({"physics": {"taxonomy": ["cd-2"]}}, "physics.taxonomy"),
    ({"physics": {"state": "fluid"}}, "physics.state"),
    ({"physics": {"windDriven": "yes"}}, "physics.windDriven"),
])
def test_bad_realism_manifests_are_rejected(tmp_path, extra, match):
    _write(tmp_path, "realism", "r", _realism(**extra))
    with pytest.raises(CatalogError, match=match):
        Catalog.load(tmp_path)


def test_applies_when_effects_must_exist(tmp_path):
    _write(tmp_path, "realism", "r", _realism(appliesWhen={"effects": ["rain"]}))
    with pytest.raises(CatalogError, match="unknown effect 'rain'"):
        Catalog.load(tmp_path)


def test_the_only_field_is_wind(tmp_path):
    _write(tmp_path, "field", "gravity", _base("gravity", kind="field", directorSelectable=False))
    with pytest.raises(CatalogError, match="only field is 'wind'"):
        Catalog.load(tmp_path)


def test_only_the_field_owns_wind_params(tmp_path):
    _write(tmp_path, "effect", "e", _base("e", kind="effect", params={
        "windSpeed": {"type": "number", "min": 0, "max": 1, "default": 0}}))
    with pytest.raises(CatalogError, match="wind params"):
        Catalog.load(tmp_path)


def test_a_window_param_is_not_a_wind_param(tmp_path):
    """night_street's windowsLit (Task 70) starts with 'wind' but is not wind."""
    _write(tmp_path, "effect", "e", _base("e", kind="effect", params={
        "windowsLit": {"type": "number", "min": 0, "max": 1, "default": 0}}))
    assert Catalog.load(tmp_path).get("effect", "e")
    _write(tmp_path / "b", "effect", "e", _base("e", kind="effect", params={
        "windDirection": {"type": "number", "min": 0, "max": 1, "default": 0}}))
    with pytest.raises(CatalogError, match="wind params"):
        Catalog.load(tmp_path / "b")


@pytest.mark.parametrize("extra,match", [({"groundType": "lava"}, "groundType"),
                                         ({"hasFoliage": "yes"}, "hasFoliage"),
                                         ({"windDefault": 20}, "windDefault")])
def test_world_physics_keys_are_validated(tmp_path, extra, match):
    _write(tmp_path, "world", "w", _base("w", **extra))
    with pytest.raises(CatalogError, match=match):
        Catalog.load(tmp_path)


@pytest.mark.parametrize("bad", [{"flies": True}, {"translates": "yes"}, ["translates"]])
def test_motion_subject_motion_is_validated(tmp_path, bad):
    _write(tmp_path, "motion", "m", _base("m", kind="motion", subjectMotion=bad))
    with pytest.raises(CatalogError, match="subjectMotion"):
        Catalog.load(tmp_path)


def test_realism_may_require_the_new_profile_facts(tmp_path):
    _write(tmp_path, "realism", "r", _realism(requiresProfile="softParts"))
    assert Catalog.load(tmp_path).get("realism", "r")["requiresProfile"] == "softParts"


def test_shipped_studio_declares_its_ground_and_still_air():
    m = Catalog.load().get("world", "studio_cyc")
    assert m["groundType"] == "studio" and m["hasFoliage"] is False and m["windDefault"] == 0.0
