import json
import pytest
from engine.catalog import Catalog, CatalogError, KINDS


def test_loads_starter_blocks():
    cat = Catalog.load()
    assert set(KINDS) == {"world", "lighting", "camera", "motion", "effect", "grade", "edit"}
    assert cat.get("world", "studio_cyc")["hasGround"] is True
    assert cat.get("camera", "arc_orbit")["framing"] == "full"
    assert cat.get("world", "moon") is None
    assert {"arc_orbit", "low_hero_push"} <= set(cat.ids("camera"))


def _write(root, kind, bid, manifest):
    d = root / kind / bid
    d.mkdir(parents=True)
    (d / "block.json").write_text(json.dumps(manifest))


def _base(bid, kind="world", **extra):
    m = {"id": bid, "kind": kind, "description": "x", "params": {},
         "subjectSizeM": [0.1, 1.0], "aspects": ["9:16"], "costWeight": 1.0,
         "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T2"}
    m.update(extra)
    return m


@pytest.mark.parametrize("bad", ["T5", "t3", 3, None])
def test_rejects_bad_tier_max(tmp_path, bad):
    _write(tmp_path, "world", "a", _base("a", tierMax=bad))
    with pytest.raises(CatalogError, match="tierMax"):
        Catalog.load(tmp_path)


def test_starter_tier_max_matches_catalog_gaps():
    # CATALOG-GAPS §3 "Suggested tierMax once fixed".
    cat = Catalog.load()
    want = {("world", "studio_cyc"): "T3", ("lighting", "softbox_three_point"): "T2",
            ("camera", "low_hero_push"): "T3", ("camera", "arc_orbit"): "T3",
            ("motion", "static"): "T3", ("grade", "neutral_film"): "T2"}
    for (kind, bid), tier in want.items():
        assert cat.get(kind, bid)["tierMax"] == tier, bid


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


# --- load_camera_path hardening -------------------------------------------------------

def _camera(bid, **extra):
    params = {
        "distance": {"type": "number", "min": 1, "max": 8, "default": 4},
        "lensMm": {"type": "number", "min": 18, "max": 135, "default": 50},
        "fstop": {"type": "number", "min": 1.4, "max": 16, "default": 4},
    }
    return _base(bid, kind="camera", framing="full", params=params, **extra)


@pytest.mark.parametrize("bad", ["nope", "../camera/c", "c/../c", "a/b", r"a\b", "..", "c/", ""])
def test_load_camera_path_rejects_unknown_or_unsafe_id(tmp_path, bad):
    _write(tmp_path, "camera", "c", _camera("c"))
    (tmp_path / "camera" / "c" / "path.py").write_text("def sample(p, prof, u):\n    return u\n")
    cat = Catalog.load(tmp_path)
    with pytest.raises(CatalogError):
        cat.load_camera_path(bad)


def test_load_camera_path_missing_path_py(tmp_path):
    _write(tmp_path, "camera", "c", _camera("c"))
    cat = Catalog.load(tmp_path)
    with pytest.raises(CatalogError, match="path.py"):
        cat.load_camera_path("c")


def test_load_camera_path_needs_callable_sample(tmp_path):
    _write(tmp_path, "camera", "c", _camera("c"))
    (tmp_path / "camera" / "c" / "path.py").write_text("sample = 3\n")
    cat = Catalog.load(tmp_path)
    with pytest.raises(CatalogError, match="sample"):
        cat.load_camera_path("c")


def test_load_camera_path_wraps_import_errors(tmp_path):
    _write(tmp_path, "camera", "c", _camera("c"))
    (tmp_path / "camera" / "c" / "path.py").write_text("raise RuntimeError('boom')\n")
    cat = Catalog.load(tmp_path)
    with pytest.raises(CatalogError, match=r"camera/c: path.py failed to import: boom") as ei:
        cat.load_camera_path("c")
    assert isinstance(ei.value.__cause__, RuntimeError)


def test_load_camera_path_caches_per_id(tmp_path):
    _write(tmp_path, "camera", "c", _camera("c"))
    f = tmp_path / "camera" / "c" / "path.py"
    f.write_text("def sample(p, prof, u):\n    return 1\n")
    cat = Catalog.load(tmp_path)
    first = cat.load_camera_path("c")
    f.write_text("def sample(p, prof, u):\n    return 2\n")
    second = cat.load_camera_path("c")
    assert first is second and second(None, None, 0) == 1


# --- block.json reading ---------------------------------------------------------------

def test_reads_block_json_with_bom(tmp_path):
    d = tmp_path / "world" / "a"
    d.mkdir(parents=True)
    (d / "block.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(_base("a")).encode("utf-8"))
    assert Catalog.load(tmp_path).get("world", "a")["id"] == "a"


def test_bad_json_raises_catalog_error(tmp_path):
    d = tmp_path / "world" / "a"
    d.mkdir(parents=True)
    (d / "block.json").write_text("{not json")
    with pytest.raises(CatalogError, match="world/a: bad block.json"):
        Catalog.load(tmp_path)


def test_non_utf8_raises_catalog_error(tmp_path):
    d = tmp_path / "world" / "a"
    d.mkdir(parents=True)
    (d / "block.json").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(CatalogError, match="world/a: bad block.json"):
        Catalog.load(tmp_path)


# --- manifest type checks -------------------------------------------------------------

@pytest.mark.parametrize("field, value, msg", [
    ("params", [], "params"),
    ("params", {"x": 5}, "param 'x'"),
    ("subjectSizeM", 1.0, "subjectSizeM"),
    ("subjectSizeM", [0.1], "subjectSizeM"),
    ("subjectSizeM", [0.1, 1.0, 2.0], "subjectSizeM"),
    ("subjectSizeM", [0.1, "1"], "subjectSizeM"),
    ("subjectSizeM", [True, 1.0], "subjectSizeM"),
    ("aspects", "9:16", "aspects"),
    ("costWeight", "1", "costWeight"),
    ("costWeight", 0, "costWeight"),
    ("costWeight", -1.0, "costWeight"),
    ("costWeight", True, "costWeight"),
    ("tags", [], "tags"),
    ("tags", {"mood": [], "energy": []}, "tags"),
    ("tags", {"mood": [], "energy": [], "palette": [], "extra": []}, "tags"),
    ("tags", {"mood": "calm", "energy": [], "palette": []}, "tags"),
    ("tags", {"mood": [1], "energy": [], "palette": []}, "tags"),
])
def test_rejects_bad_manifest_types(tmp_path, field, value, msg):
    _write(tmp_path, "world", "a", _base("a", **{field: value}))
    with pytest.raises(CatalogError, match=msg) as ei:
        Catalog.load(tmp_path)
    assert "world/a" in str(ei.value)


def test_type_errors_surface_before_id_mismatch(tmp_path):
    _write(tmp_path, "world", "a", _base("b", costWeight="heavy"))
    with pytest.raises(CatalogError, match="costWeight"):
        Catalog.load(tmp_path)


def test_bool_param_bounds_rejected(tmp_path):
    _write(tmp_path, "world", "a", _base("a", params={"x": {"type": "number", "min": False, "max": 1, "default": True}}))
    with pytest.raises(CatalogError, match="numeric"):
        Catalog.load(tmp_path)


# --- folder scanning ------------------------------------------------------------------

def test_unknown_kind_folder_raises(tmp_path):
    _write(tmp_path, "world", "a", _base("a"))
    (tmp_path / "weather").mkdir()
    with pytest.raises(CatalogError, match="unknown kind folder"):
        Catalog.load(tmp_path)


def test_block_folder_missing_block_json_raises(tmp_path):
    (tmp_path / "world" / "empty").mkdir(parents=True)
    with pytest.raises(CatalogError, match="world/empty"):
        Catalog.load(tmp_path)


# --- get() isolation ------------------------------------------------------------------

def test_get_returns_a_copy(tmp_path):
    _write(tmp_path, "world", "a", _base("a"))
    cat = Catalog.load(tmp_path)
    m = cat.get("world", "a")
    m["tags"]["mood"].append("hacked")
    m["id"] = "zzz"
    fresh = cat.get("world", "a")
    assert fresh["id"] == "a" and fresh["tags"]["mood"] == []


def test_manifest_must_be_an_object(tmp_path):
    d = tmp_path / "world" / "a"
    d.mkdir(parents=True)
    (d / "block.json").write_text("[1, 2]")
    with pytest.raises(CatalogError, match="world/a: block.json must be an object"):
        Catalog.load(tmp_path)


def test_camera_distance_min_must_be_positive(tmp_path):
    # The checker searches distance on a log grid; a zero/negative min would crash it.
    m = _camera("c")
    m["params"]["distance"].update({"min": 0, "default": 4})
    _write(tmp_path, "camera", "c", m)
    with pytest.raises(CatalogError, match="distance min must be > 0"):
        Catalog.load(tmp_path)
