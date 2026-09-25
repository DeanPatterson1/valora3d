import ast
import json
from pathlib import Path

import pytest

from engine.director.family import FAMILIES, family
from engine.profile import SubjectProfile

ENGINE = Path(__file__).resolve().parents[1]
PROFILES = ENGINE / "tests" / "fixtures" / "profiles"


def _p(name):
    return SubjectProfile.from_dict(json.loads((PROFILES / f"{name}.json").read_text(encoding="utf-8")))


@pytest.mark.parametrize("name,fam", [("sports_car", "vehicle"), ("pocket_watch", "product"),
                                      ("sneaker", "product"), ("mid_century_lounge_chair", "furniture"),
                                      ("cesium_man", "character")])
def test_family_hint(name, fam):
    assert family(_p(name)) == fam and fam in FAMILIES


def _module_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:  # module level only; imports inside functions are lazy and allowed
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_engine_never_imports_the_sdk_at_module_level():
    for f in ENGINE.rglob("*.py"):
        if "tests" in f.parts:
            continue
        assert "anthropic" not in _module_imports(f), f


def test_compiler_and_blender_code_never_import_the_director():
    for f in list((ENGINE / "compiler").glob("*.py")) + list((ENGINE / "blender").glob("*.py")) + list(
            (ENGINE / "blocks").rglob("*.py")):
        assert not any(m.startswith("engine.director") for m in _module_imports(f)), f
