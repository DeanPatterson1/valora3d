import ast
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.craft_rules import score_script
from engine.director.repair import (AUTO_FIX, ERROR_HINTS, S_REPAIRS, auto_fix_craft, craft_failures,
                                    problems)
from engine.director.rulebook import EXAMPLES_DIR, example_script
from engine.issues import Issue
from engine.tests.test_director_package import _p

ENGINE = Path(__file__).resolve().parents[1]
DIRECTOR_CODES = {"llm_not_json", "llm_stop_refusal", "llm_stop_max_tokens", "director_block_forbidden"}


def engine_error_codes():
    """Every Issue code the engine can raise with severity 'error' (AST scan, so new codes are caught)."""
    codes = {"bad_format", "bad_subject"}  # f"bad_{key}" in script.py
    for f in ENGINE.rglob("*.py"):
        if "tests" in f.parts or "director" in f.parts:
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", None))
                a = node.args
                if (name == "Issue" and len(a) >= 4 and isinstance(a[0], ast.Constant)
                        and isinstance(a[3], ast.Constant) and a[3].value == "error"):
                    codes.add(a[0].value)
                elif name == "err" and a and isinstance(a[0], ast.Constant):
                    codes.add(a[0].value)
            elif (f.name == "markers.py" and isinstance(node, ast.Tuple) and len(node.elts) == 2
                  and isinstance(node.elts[0], ast.Constant) and isinstance(node.elts[0].value, str)
                  and "_" in node.elts[0].value and node.elts[0].value.islower()):
                codes.add(node.elts[0].value)
    return codes


def test_every_error_code_has_a_hint():
    missing = sorted((engine_error_codes() | DIRECTOR_CODES) - set(ERROR_HINTS))
    assert missing == [], f"add ERROR_HINTS for {missing}"


def test_every_script_item_has_a_repair_entry():
    cat = Catalog.load()
    for f in EXAMPLES_DIR.glob("*.json"):
        ex = json.loads(f.read_text(encoding="utf-8"))
        r = check(example_script(ex), _p(ex["profile"]), cat)
        ids = {x.id for x in score_script(r.script, _p(ex["profile"]), cat)}
        assert ids <= set(S_REPAIRS), sorted(ids - set(S_REPAIRS))


def _vehicle():
    ex = json.loads((EXAMPLES_DIR / "vehicle_empty.json").read_text(encoding="utf-8"))
    return check(example_script(ex), _p("sports_car"), Catalog.load()).script


def test_auto_fix_lens_and_depth_on_vehicle_full_frames():
    cat, car = Catalog.load(), _p("sports_car")
    s = _vehicle()
    s["shots"][0]["camera"]["params"].update(lensMm=20.0)
    s["shots"][2]["camera"]["params"].update(fstop=1.4)
    fails = craft_failures(s, car, cat)
    assert {"V-C02", "T3-21"} <= {f.id for f in fails}
    fixed, issues = auto_fix_craft(s, fails, car, cat)
    assert fixed["shots"][0]["camera"]["params"]["lensMm"] == 28.0
    assert fixed["shots"][2]["camera"]["params"]["fstop"] == 8.0
    assert {i.code for i in issues} >= {"craft_lens_28", "craft_deep_focus"}
    assert s["shots"][0]["camera"]["params"]["lensMm"] == 20.0  # input untouched
    assert set(AUTO_FIX) == {"T2-03", "T3-13", "V-C02", "T3-21"}


def test_problems_report_errors_and_craft_with_fixes():
    craft = craft_failures({**_vehicle(), "shots": _vehicle()["shots"][:1]}, _p("sports_car"), Catalog.load())
    out = problems([Issue("unknown_block", "world.id", "no world 'moon'", "error"),
                    Issue("param_clamped", "x", "y", "repaired")], craft)
    assert out[0] == {"code": "unknown_block", "path": "world.id", "message": "no world 'moon'",
                      "fix": ERROR_HINTS["unknown_block"]}
    assert all(p["code"] != "param_clamped" for p in out)          # repairs are not reported back
    assert any(p["code"] == "T3-01" for p in out)                   # 1 shot in 10 s
