import json
import pytest
from engine.catalog import Catalog, CatalogError, KINDS


def test_loads_starter_blocks():
    cat = Catalog.load()
    assert set(KINDS) == {"world", "lighting", "camera", "motion", "effect", "grade"}
    assert cat.get("world", "studio_cyc")["hasGround"] is True
    assert cat.get("camera", "arc_orbit")["framing"] == "full"
    assert cat.get("world", "moon") is None
    assert sorted(cat.ids("camera")) == ["arc_orbit", "low_hero_push"]


def _write(root, kind, bid, manifest):
    d = root / kind / bid
    d.mkdir(parents=True)
    (d / "block.json").write_text(json.dumps(manifest))


def _base(bid, kind="world", **extra):
    m = {"id": bid, "kind": kind, "description": "x", "params": {},
         "subjectSizeM": [0.1, 1.0], "aspects": ["9:16"], "costWeight": 1.0,
         "tags": {"mood": [], "energy": [], "palette": []}}
    m.update(extra)
    return m


def test_rejects_id_folder_mismatch(tmp_path):
    _write(tmp_path, "world", "a", _base("b"))
    with pytest.raises(CatalogError, match="id 'b' does not match folder 'a'"):
        Catalog.load(tmp_path)


def test_rejects_bad_param_spec(tmp_path):
    _write(tmp_path, "world", "a", _base("a", params={"x": {"type": "number", "min": 2, "max": 1, "default": 1}}))
    with pytest.raises(CatalogError, match="min > max"):
        Catalog.load(tmp_path)


def test_rejects_default_outside_range(tmp_path):
    _write(tmp_path, "world", "a", _base("a", params={"x": {"type": "number", "min": 0, "max": 1, "default": 5}}))
    with pytest.raises(CatalogError, match="default outside"):
        Catalog.load(tmp_path)


def test_camera_needs_framing_and_core_params(tmp_path):
    _write(tmp_path, "camera", "c", _base("c", kind="camera"))
    with pytest.raises(CatalogError, match="camera 'c' missing"):
        Catalog.load(tmp_path)
