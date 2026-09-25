"""Every Issue code the engine can emit is registered with its severity, so the growth contract can say
'this block is guarded by gate X' and a typo in a code name fails a test instead of shipping silently."""
import ast
from pathlib import Path

from engine.gates import CODES, SEVERITIES
from engine.tests.test_director_repair import engine_error_codes

ROOT = Path(__file__).resolve().parents[1]

# Codes built at run time (the scan cannot see them): code -> (file, the literal prefix it is built from).
DYNAMIC = {
    "bad_format": ("script.py", 'f"bad_{key}"'), "bad_subject": ("script.py", 'f"bad_{key}"'),
    "direction_world": ("director/adherence.py", 'f"direction_{axis}"'),
    "direction_opener": ("director/adherence.py", 'f"direction_{axis}"'),
    "llm_stop_refusal": ("director/pipeline.py", 'f"llm_stop_{res.stop_reason}"'),
    "llm_stop_max_tokens": ("director/pipeline.py", 'f"llm_stop_{res.stop_reason}"'),
    "craft_eased": ("director/repair.py", '"craft_eased"'), "craft_settled": ("director/repair.py", '"craft_settled"'),
    "craft_lens_28": ("director/repair.py", '"craft_lens_28"'),
    "craft_deep_focus": ("director/repair.py", '"craft_deep_focus"'),
}


def _emitted():
    """code -> set of severities it is emitted with (literal Issue calls, the err() helpers and marker
    tuples via test_director_repair.engine_error_codes, and the DYNAMIC allowlist)."""
    found = {}
    for f in ROOT.rglob("*.py"):
        if "tests" in f.parts or "__pycache__" in f.parts:
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "Issue"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                sev = node.args[3].value if len(node.args) >= 4 and isinstance(node.args[3], ast.Constant) else None
                found.setdefault(node.args[0].value, set()).add(sev)
    for code in engine_error_codes():
        found.setdefault(code, set()).add("error")
    for code in DYNAMIC:
        found.setdefault(code, set()).add(CODES.get(code))
    return found


def test_dynamic_codes_still_come_from_their_source():
    for code, (rel, needle) in DYNAMIC.items():
        assert needle in (ROOT / rel).read_text(encoding="utf-8"), (code, rel, needle)


def test_every_emitted_code_is_registered():
    missing = sorted(set(_emitted()) - set(CODES))
    assert not missing, f"register these in engine/gates.py: {missing}"


def test_registry_has_no_dead_codes_and_valid_severities():
    dead = sorted(set(CODES) - set(_emitted()))
    assert not dead, f"registered but never emitted: {dead}"
    assert all(sev in SEVERITIES for sev in CODES.values())


def test_registered_severity_is_the_strictest_emitted():
    for code, sevs in _emitted().items():
        known = [s for s in sevs if s in SEVERITIES]
        if known and code in CODES:
            assert CODES[code] == max(known, key=SEVERITIES.index), (code, sorted(known), CODES[code])
