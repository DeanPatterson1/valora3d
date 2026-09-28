"""The bake key hashes the engine modules a sim block's bake imports (engine/bake/deps.py), so an edited helper
(engine/blender/pieces.py, gn_sim.py, engine/physics/*) re-keys every cache built from it. Replaces the hand-kept
MESH_REV numbers lane R carried (the T98 block_sha finding)."""
from pathlib import Path

import pytest

from engine.bake.deps import ENGINE, bake_sources, imported_modules
from engine.bake.key import sha256_files
from engine.catalog import Catalog

SIM = ENGINE / "blocks" / "sim"


def _rel(paths):
    return {Path(p).resolve().relative_to(ENGINE).as_posix() for p in paths}


def _write(root, rel, text=""):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def tree(tmp_path):
    """A tiny engine package plus one block whose bake imports a helper inside its function."""
    eng = tmp_path / "engine"
    _write(eng, "__init__.py")
    _write(eng, "blender/__init__.py")
    _write(eng, "physics/__init__.py")
    _write(eng, "bake/__init__.py")
    _write(eng, "bake/run.py", "X = 1\n")
    _write(eng, "blender/helper.py", "from engine.physics import deep\nfrom . import sibling\nimport bpy\n")
    _write(eng, "blender/sibling.py", "import json\n")
    _write(eng, "physics/deep.py", "K = 0.6\n")
    _write(eng, "physics/unused.py", "K = 1\n")
    blk = tmp_path / "blocks" / "sim" / "_t"
    _write(blk, "bake.py", "import json\n\n\ndef bake(ctx):\n    import bpy\n"
                           "    from engine.blender import helper as H\n    from engine.bake.run import X\n")
    _write(blk, "build.py", "from engine.bake.run import X\nfrom engine.physics import unused\n")
    return eng, blk


def test_function_level_transitive_and_relative_imports_are_followed(tree):
    eng, blk = tree
    src = bake_sources(blk, eng)
    assert src[:2] == [blk / "bake.py", blk / "build.py"]
    rel = {p.resolve().relative_to(eng.resolve()).as_posix() for p in src[2:]}
    assert {"blender/helper.py", "blender/sibling.py", "physics/deep.py"} <= rel
    assert "bake/run.py" not in rel          # stage-4b plumbing is not the block's physics
    assert "physics/unused.py" not in rel    # build.py's imports read a cache, they do not make it


def test_editing_a_deep_helper_changes_the_block_sha(tree):
    eng, blk = tree
    before = sha256_files(bake_sources(blk, eng))
    (eng / "physics" / "deep.py").write_text("K = 0.7\n", encoding="utf-8")
    assert sha256_files(bake_sources(blk, eng)) != before


def test_the_sources_order_is_stable(tree):
    eng, blk = tree
    assert bake_sources(blk, eng) == bake_sources(blk, eng)


def test_editing_a_shipped_helper_rekeys_the_block(tmp_path, monkeypatch):
    """engine/bake/run.block_sha over a real block: rigid_scatter's key moves when pieces.py changes."""
    from engine.bake import run
    cat = Catalog.load()
    if "rigid_scatter" not in cat.ids("sim"):
        pytest.skip("rigid_scatter not shipped")
    before = run.block_sha(cat, "rigid_scatter")
    pieces = ENGINE / "blender" / "pieces.py"
    real = pieces.read_bytes()
    import engine.bake.key as K
    orig = K.sha256_file

    def fake(path, chunk=1 << 20):
        return "edited" if Path(path).resolve() == pieces.resolve() else orig(path, chunk)
    monkeypatch.setattr(K, "sha256_file", fake)
    assert run.block_sha(cat, "rigid_scatter") != before
    assert pieces.read_bytes() == real


@pytest.mark.parametrize("bid", sorted(d.name for d in SIM.iterdir() if (d / "bake.py").is_file()))
def test_every_engine_module_a_shipped_bake_imports_is_hashed(bid):
    d = SIM / bid
    src = _rel(bake_sources(d)[2:])
    for name in imported_modules(d / "bake.py"):
        if name.startswith("engine.bake"):
            continue
        parts = name.split(".")[1:]
        mod, pkg = "/".join(parts) + ".py", "/".join(parts + ["__init__.py"])
        if (ENGINE / mod).is_file():
            assert mod in src, (bid, name)
        elif (ENGINE / pkg).is_file():
            assert pkg in src, (bid, name)


def test_no_block_needs_a_hand_bumped_mesh_revision():
    for f in SIM.glob("*/bake.py"):
        assert "MESH_REV" not in f.read_text(encoding="utf-8"), f


# Shared fix C (phase 6): the particle helpers lane P named as the stale-cache risk are in every key that uses them.
HELPER_USERS = {
    "blender/gn_sim.py": ("bubbles", "confetti", "sparks", "runners", "tyre_spray", "dust_kick"),
    "physics/gn_sim.py": ("bubbles", "confetti", "sparks", "runners"),
    "blender/particle_pack.py": ("bubbles", "confetti", "sparks"),
    "physics/particle_pack.py": ("bubbles", "confetti", "sparks"),
    "blender/road_spray.py": ("tyre_spray", "dust_kick"),
    "physics/road_spray.py": ("tyre_spray", "dust_kick"),
    "blender/runners.py": ("runners",),
    "physics/runners.py": ("runners",),
}


@pytest.mark.parametrize("helper,bid", [(h, b) for h, bs in HELPER_USERS.items() for b in bs])
def test_an_edited_particle_helper_rekeys_the_blocks_that_bake_with_it(helper, bid, monkeypatch):
    from engine.bake import run
    import engine.bake.key as K
    cat = Catalog.load()
    if bid not in cat.ids("sim"):
        pytest.skip(f"{bid} not shipped")
    assert helper in _rel(bake_sources(SIM / bid)[2:]), (bid, helper)
    before = run.block_sha(cat, bid)
    target, orig = (ENGINE / helper).resolve(), K.sha256_file
    monkeypatch.setattr(K, "sha256_file", lambda p, chunk=1 << 20: "edited" if Path(p).resolve() == target
                        else orig(p, chunk))
    assert run.block_sha(cat, bid) != before
