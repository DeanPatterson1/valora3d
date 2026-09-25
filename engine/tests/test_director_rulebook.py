import json

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.craft_rules import score_script
from engine.director.rulebook import EXAMPLES_DIR, RULEBOOK, build_rulebook, example_script, load_rulebook
from engine.tests.test_director_package import _p

EXAMPLES = sorted(EXAMPLES_DIR.glob("*.json"))


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_examples_pass_the_checker_and_every_t2_t3_script_item(path):
    ex = json.loads(path.read_text(encoding="utf-8"))
    cat = Catalog.load()
    r = check(example_script(ex), _p(ex["profile"]), cat)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    fails = [x.id for x in score_script(r.script, _p(ex["profile"]), cat)
             if x.status == "fail" and x.id[:2] in ("T1", "T2", "T3", "V-")]
    assert fails == []


def test_committed_rulebook_is_current():
    assert RULEBOOK.read_text(encoding="utf-8") == build_rulebook(Catalog.load()), \
        "regenerate: py -m engine.director.rulebook --write"


def test_rulebook_sections_size_and_version():
    text, version = load_rulebook()
    for h in ("# Valora3D director rulebook", "# 1. Menu", "# 2. Taste guide", "# 3. Hard rules",
              "# 4. When the prompt says little", "# 5. Checked examples"):
        assert h in text
    assert 512 * 4 < len(text) < 30000 * 4          # cacheable (>= 512 tokens), well under budget
    menu = text.split("# 1. Menu")[1].split("# 2.")[0]
    assert len(version) == 12 and "camera/turntable" not in menu and "camera.turntable" not in menu
