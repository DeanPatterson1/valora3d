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


# ---- review chunk 2 #1-#3: dependency sets, containment, one validator, credits ----

def _doc(**assets):
    return {"schema": "valora.assets/1", "assets": assets}


def _entry(path, data, licence="CC0-1.0", credit=None):
    import hashlib
    return {"path": path, "sha256": hashlib.sha256(data).hexdigest(), "licence": licence,
            "source": "https://x", "credit": credit}


def _gltf_lib(tmp_path, *, pin_bin=True, pin_tex=True, bin_bytes=b"BIN"):
    g = json.dumps({"buffers": [{"uri": "m.bin"}], "images": [{"uri": "textures/t.jpg"}, {"uri": "data:image/png;base64,AA"}]}).encode()
    (tmp_path / "lib" / "m" / "textures").mkdir(parents=True)
    (tmp_path / "lib" / "m" / "m.gltf").write_bytes(g)
    (tmp_path / "lib" / "m" / "m.bin").write_bytes(bin_bytes)
    (tmp_path / "lib" / "m" / "textures" / "t.jpg").write_bytes(b"TEX")
    assets = {"m": _entry("m/m.gltf", g)}
    if pin_bin:
        assets["m_bin"] = _entry("m/m.bin", b"BIN")
    if pin_tex:
        assets["m_tex"] = _entry("m/textures/t.jpg", b"TEX")
    return tmp_path / "lib", _doc(**assets)


def test_gltf_resolves_only_with_its_whole_dependency_set(tmp_path):
    from engine.assets import resolve_gltf
    root, doc = _gltf_lib(tmp_path)
    assert resolve_gltf("m", root=root, manifest=doc) == root / "m" / "m.gltf"


def test_gltf_with_a_tampered_buffer_is_refused(tmp_path):
    from engine.assets import resolve_gltf
    root, doc = _gltf_lib(tmp_path, bin_bytes=b"EVIL")
    with pytest.raises(AssetError):
        resolve_gltf("m", root=root, manifest=doc)


def test_gltf_with_an_unpinned_texture_is_refused(tmp_path):
    from engine.assets import resolve_gltf
    root, doc = _gltf_lib(tmp_path, pin_tex=False)
    with pytest.raises(AssetError, match="not pinned"):
        resolve_gltf("m", root=root, manifest=doc)


def test_gltf_with_a_missing_buffer_falls_back(tmp_path):
    from engine.assets import resolve_gltf
    root, doc = _gltf_lib(tmp_path)
    (root / "m" / "m.bin").unlink()
    assert resolve_gltf("m", root=root, manifest=doc) is None       # procedural fallback, never a broken import


def test_gltf_dependency_escaping_the_library_is_refused(tmp_path):
    from engine.assets import resolve_gltf
    root, doc = _gltf_lib(tmp_path)
    g = json.dumps({"buffers": [{"uri": "../../outside.bin"}]}).encode()
    (root / "m" / "m.gltf").write_bytes(g)
    doc["assets"]["m"] = _entry("m/m.gltf", g)
    with pytest.raises(AssetError):
        resolve_gltf("m", root=root, manifest=doc)


def test_the_courtyard_imports_gltfs_only_through_the_dependency_check():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "blocks" / "world" / "rain_courtyard" / "build.py").read_text(encoding="utf-8")
    assert 'resolve_gltf("grass_medium_01_1k")' in src and 'resolve_gltf("tree_small_02_1k")' in src
    assert 'resolve("grass_medium_01_1k")' not in src and 'resolve("tree_small_02_1k")' not in src


def test_every_pinned_gltf_has_its_dependencies_pinned():
    from pathlib import PurePosixPath
    from engine.assets import library_root, gltf_dependencies
    doc = load_manifest()
    paths = {a["path"] for a in doc["assets"].values()}
    checked = 0
    for aid, a in doc["assets"].items():
        p = library_root() / a["path"]
        if a["path"].endswith(".gltf") and p.exists():
            for uri in gltf_dependencies(p):
                assert str(PurePosixPath(a["path"]).parent / uri) in paths, (aid, uri)
            checked += 1
    if checked == 0:
        pytest.skip("library not on disk")


@pytest.mark.parametrize("bad", ["../outside.png", "a/../../x.png", "/etc/passwd", "C:/Windows/x.png",
                                 r"a\..\x.png", "", "a//b.png"])
def test_manifest_paths_that_escape_are_refused(tmp_path, bad):
    doc = _doc(x=_entry(bad, b"px"))
    with pytest.raises(AssetError):
        resolve("x", root=tmp_path, manifest=doc)


def test_symlink_escaping_the_library_is_refused(tmp_path):
    import os
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.png").write_bytes(b"px")
    lib = tmp_path / "lib"
    lib.mkdir()
    try:
        os.symlink(outside, lib / "link", target_is_directory=True)
    except (OSError, NotImplementedError):
        try:                                                 # Windows without symlink rights: a junction escapes the same way
            import _winapi
            _winapi.CreateJunction(str(outside), str(lib / "link"))
        except (ImportError, OSError):
            pytest.skip("neither symlinks nor junctions permitted here")
    with pytest.raises(AssetError, match="outside"):
        resolve("x", root=lib, manifest=_doc(x=_entry("link/x.png", b"px")))


def test_a_passed_in_manifest_gets_the_same_licence_check(tmp_path):
    (tmp_path / "x.png").write_bytes(b"px")
    with pytest.raises(AssetError, match="not shippable"):
        resolve("x", root=tmp_path, manifest=_doc(x=_entry("x.png", b"px", licence="CC-BY-NC-4.0")))


def test_cc_by_credit_must_match_a_credits_row(tmp_path):
    from engine.assets import credit_rows, validate_manifest
    credits = tmp_path / "CREDITS.md"
    credits.write_text("| Asset id | Author | Source | Licence |\n|---|---|---|---|\n"
                       "| x | Jane Doe | https://x | CC-BY-4.0 |\n", encoding="utf-8")
    rows = credit_rows(credits)
    assert rows == {"x": "Jane Doe"}
    validate_manifest(_doc(x=_entry("x.png", b"px", "CC-BY-4.0", "Jane Doe")), rows)
    with pytest.raises(AssetError, match="CREDITS"):
        validate_manifest(_doc(x=_entry("x.png", b"px", "CC-BY-4.0", "Someone Else")), rows)
    with pytest.raises(AssetError, match="CREDITS"):
        validate_manifest(_doc(y=_entry("y.png", b"px", "CC-BY-4.0", "Jane Doe")), rows)


def _run_import(tmp_path, monkeypatch, records, files):
    import tools.assets.import_local as IL
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest.json").write_text(json.dumps(records), encoding="utf-8")
    for rel, data in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    monkeypatch.setattr(IL, "DEST", tmp_path / "dest")
    monkeypatch.setattr(IL, "MANIFEST", tmp_path / "manifest.json")
    IL.main(["--source", str(src)])
    return json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["assets"]


def test_import_local_refuses_traversal_and_absolute_records(tmp_path, monkeypatch):
    import hashlib
    evil = b"secret"
    md5 = hashlib.md5(evil).hexdigest()
    recs = [{"file": "tree_small_02/../../outside.bin", "license": "CC0", "md5": md5, "source": "https://polyhaven.com/a/t"},
            {"file": "tree_small_02/../../../dest_escape.bin", "license": "CC0", "md5": md5, "source": "https://polyhaven.com/a/t"}]
    got = _run_import(tmp_path, monkeypatch, recs, {"outside.bin": evil})
    assert got == {}
    assert not (tmp_path / "dest_escape.bin").exists()
    assert not (tmp_path / "dest").exists() or not any((tmp_path / "dest").rglob("*"))


def test_import_local_still_imports_a_clean_record(tmp_path, monkeypatch):
    import hashlib
    data = b"tree"
    recs = [{"file": "tree_small_02/t.bin", "license": "CC0", "md5": hashlib.md5(data).hexdigest(),
             "source": "https://polyhaven.com/a/tree_small_02"}]
    got = _run_import(tmp_path, monkeypatch, recs, {"src/tree_small_02/t.bin": data})
    assert got["t_bin"]["path"] == "polyhaven/tree_small_02/t.bin"
    assert (tmp_path / "dest" / "tree_small_02" / "t.bin").read_bytes() == data
