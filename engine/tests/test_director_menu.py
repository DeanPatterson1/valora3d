import json
import shutil

from engine.catalog import BLOCKS_DIR, Catalog
from engine.director.menu import render_menu


def test_menu_lists_every_selectable_block_param_and_range():
    cat = Catalog.load()
    text = render_menu(cat)
    for kind in ("world", "lighting", "camera", "motion", "effect", "grade", "edit"):
        for bid in cat.selectable_ids(kind):
            m = cat.get(kind, bid)
            assert f"### {kind}/{bid}" in text
            for name in m["params"]:
                assert f"- {name}:" in text
    assert "lensMm: number 85..150 (default 100)" in text
    assert "capabilities: camera.macro" in text


def test_menu_never_shows_the_turntable():
    text = render_menu(Catalog.load())
    assert "camera/turntable" not in text and "camera.turntable" not in text


def test_menu_is_deterministic_and_follows_the_manifests(tmp_path):
    root = tmp_path / "blocks"
    shutil.copytree(BLOCKS_DIR, root, ignore=shutil.ignore_patterns("__pycache__"))
    a = render_menu(Catalog.load(root))
    assert a == render_menu(Catalog.load(root))
    f = root / "camera" / "macro_detail" / "block.json"
    m = json.loads(f.read_text(encoding="utf-8"))
    m["params"]["lensMm"]["max"] = 180.0
    f.write_text(json.dumps(m), encoding="utf-8")
    assert "lensMm: number 85..180 (default 100)" in render_menu(Catalog.load(root))
