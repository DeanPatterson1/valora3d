"""Task 62: pinned, licence-clean assets with procedural fallbacks (blocks never download)."""
import json

import pytest

from engine.assets import ALLOWED_LICENCES, AssetError, load_manifest, resolve


def test_manifest_entries_are_licence_clean_and_pinned():
    assets = load_manifest()["assets"]
    assert assets, "import_local.py has not been run"
    for aid, a in assets.items():
        assert a["licence"] in ALLOWED_LICENCES, aid
        assert len(a["sha256"]) == 64 and a["source"].startswith(("https://", "owned:")), aid
        if a["licence"] == "CC-BY-4.0":
            assert a.get("credit"), aid


def test_the_planned_assets_are_pinned_and_the_8k_is_not():
    ids = set(load_manifest()["assets"])
    assert {"cloudy_vondelpark_4k", "asphalt_02_diff", "asphalt_02_rough", "asphalt_02_nor_gl", "asphalt_02_disp",
            "tree_small_02_1k", "grass_medium_01_1k"} <= ids
    assert not any("8k" in a for a in ids)


def test_missing_file_falls_back_never_raises(tmp_path):
    got = resolve("asphalt_02_diff", root=tmp_path)          # nothing on disk
    assert got is None                                        # caller builds the procedural fallback


def test_hash_mismatch_is_refused(tmp_path):
    m = load_manifest()
    aid, a = next(iter(m["assets"].items()))
    p = tmp_path / a["path"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"not the asset")
    with pytest.raises(AssetError):
        resolve(aid, root=tmp_path)


def test_matching_file_resolves(tmp_path):
    import hashlib
    doc = {"schema": "valora.assets/1", "assets": {"x": {"path": "a/x.png", "sha256": hashlib.sha256(b"px").hexdigest(),
                                                         "licence": "CC0-1.0", "source": "https://x"}}}
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.png").write_bytes(b"px")
    assert resolve("x", root=tmp_path, manifest=doc) == tmp_path / "a" / "x.png"
    with pytest.raises(AssetError):
        resolve("nope", root=tmp_path, manifest=doc)


def test_unknown_licence_rejected(tmp_path, monkeypatch):
    import engine.assets as A
    doc = {"schema": "valora.assets/1", "assets": {"x": {"path": "x.png", "sha256": "0" * 64, "licence": "CC-BY-NC-4.0", "source": "https://x"}}}
    f = tmp_path / "m.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(AssetError):
        A.load_manifest(f)


def test_cc_by_needs_a_credit(tmp_path):
    import engine.assets as A
    doc = {"schema": "valora.assets/1", "assets": {"x": {"path": "x.png", "sha256": "0" * 64, "licence": "CC-BY-4.0",
                                                         "source": "https://x", "credit": None}}}
    f = tmp_path / "m.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(AssetError):
        A.load_manifest(f)
