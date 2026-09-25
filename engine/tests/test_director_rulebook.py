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


def test_example_profiles_ship_with_the_director_not_the_tests():
    from engine.director.rulebook import PROFILES
    assert PROFILES == EXAMPLES_DIR / "profiles" and "tests" not in PROFILES.parts
    for f in EXAMPLES_DIR.glob("*.json"):
        assert (PROFILES / f"{json.loads(f.read_text(encoding='utf-8'))['profile']}.json").is_file(), f.name


# --- phase 5 Task 86: the menu, taste and default text cover the grown catalog ---------------------------

GROWTH = json.loads((EXAMPLES_DIR.parents[1] / "catalog_growth.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("ref", sorted(GROWTH["blocks"]))
def test_every_growth_block_is_on_the_menu_with_its_description_and_ranges(ref):
    from engine.director.menu import _f
    kind, bid = ref.split("/")
    m = Catalog.load().get(kind, bid)
    menu = load_rulebook()[0].split("# 1. Menu")[1].split("# 2.")[0]
    card = menu.split(f"### {ref}  (")[1].split("\n### ")[0]
    assert m["description"] in card
    for name, spec in m["params"].items():
        if spec["type"] == "number":
            assert f"- {name}: number {_f(spec['min'])}..{_f(spec['max'])}" in card, (ref, name)


def test_taste_rules_validate_and_render_any_first():
    from engine.director.taste import load_rules, validate_rules
    rules = load_rules()
    assert validate_rules(rules, Catalog.load()) == []
    taste = load_rulebook()[0].split("# 2. Taste guide")[1].split("# 3.")[0]
    ids = [r["id"] for r in rules]
    assert all(f"TG-{n}" in taste for n in range(24, 47) if f"TG-{n}" in ids)
    heads = [ln for ln in taste.splitlines() if ln.startswith("## ")]
    assert heads[0] == "## All subjects"                                   # family any first, then per family
    anys = [r["id"] for r in rules if r["family"] == "any" and r["id"] in taste]
    assert anys and all(taste.find(i) < taste.find("## Vehicles") for i in anys)
    assert len(taste) < 12000   # (eng) no phase-3 budget constant exists; 9310 chars measured at Task 86


def test_default_text_names_world_weather_and_wind_from_the_direction():
    text = load_rulebook()[0].split("# 4. When the prompt says little")[1].split("# 5.")[0]
    assert "weather" in text and "wind" in text and "world" in text and "Never add motion" in text
