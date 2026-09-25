"""Every Issue code the engine can emit is registered with its severity, so the growth contract can say
'this block is guarded by gate X' and a typo in a code name fails a test instead of shipping silently.

The scan reads the tree, never the registry (review of chunk 0, #4/#5):
- `Issue(...)` calls with the code and severity positional OR keyword;
- helpers whose parameter is passed on as the code (`err(code, ...)`, `setp(i, key, value, code)`): each
  call of the helper in the same file must pass a literal, or a name bound by an enclosing literal loop;
- f-string codes resolved from the enclosing `for x in (...)` loop or `if x in (...)` guard;
- anything else must be an exhaustively checked DYNAMIC_SITES entry with its own resolver; an unresolved
  emission site fails.
The severity always comes from the emitting call, so the registry's severity is checked, not echoed."""
import ast
from pathlib import Path

from engine.gates import CODES, SEVERITIES

ROOT = Path(__file__).resolve().parents[1]


def _parents(tree):
    par = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            par[c] = n
    return par


def _arg(call, idx, name):
    if len(call.args) > idx:
        return call.args[idx]
    return next((k.value for k in call.keywords if k.arg == name), None)


def _str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _consts(node):
    """A tuple/list of literals -> list of their values, else None."""
    if isinstance(node, (ast.Tuple, ast.List)) and all(isinstance(e, ast.Constant) for e in node.elts):
        return [e.value for e in node.elts]
    return None


def _values_of(expr, at, par):
    """Literal values `expr` can take at node `at`: a literal, or a name/attribute bound by an enclosing
    `for` over literals (plain or tuple target) or guarded by an enclosing `if <expr> in (literals)`.
    None when it cannot be resolved."""
    if _str(expr) is not None:
        return {expr.value}
    key, n = ast.unparse(expr), at
    while n in par:
        child, n = n, par[n]
        if isinstance(n, ast.For):
            if ast.unparse(n.target) == key and _consts(n.iter) is not None:
                return set(_consts(n.iter))
            if isinstance(n.target, ast.Tuple) and isinstance(n.iter, (ast.Tuple, ast.List)):
                names = [ast.unparse(t) for t in n.target.elts]
                rows = [_consts(r) for r in n.iter.elts]
                if key in names and all(r is not None and len(r) == len(names) for r in rows):
                    return {r[names.index(key)] for r in rows}
        if isinstance(n, ast.If) and child in n.body and isinstance(n.test, ast.Compare):
            t = n.test
            if (ast.unparse(t.left) == key and len(t.ops) == 1 and isinstance(t.ops[0], ast.In)
                    and _consts(t.comparators[0]) is not None):
                return set(_consts(t.comparators[0]))
    return None


def _fstring_codes(js, at, par):
    parts = [[]]
    for v in js.values:
        if isinstance(v, ast.Constant):
            parts = [p + [v.value] for p in parts]
        else:
            vals = _values_of(v.value, at, par)
            if vals is None:
                return None
            parts = [p + [str(x)] for p in parts for x in sorted(vals)]
    return {"".join(p) for p in parts}


# --- resolvers for the sites a generic rule cannot read ------------------------------------------------

def _marker_tuples(tree, **_):
    """markers.py builds codes as ("code", "message") tuples returned by _marker_errors/_part_error."""
    return {n.elts[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Tuple) and len(n.elts) == 2 and _str(n.elts[0]) and "_" in n.elts[0].value
            and n.elts[0].value.islower() and " " not in n.elts[0].value}


def _direction_axes(tree, fn, **_):
    """adherence.enforce_direction: `for axis in drift(...)`; the final else emits direction_{axis} for
    every axis drift() can return that no earlier branch handles."""
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    axes = set()
    for n in ast.walk(funcs["drift"]):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "append" and _str(n.args[0]):
            axes.add(n.args[0].value)
    paths = next(n.value for n in tree.body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "_PATHS")
    axes |= {k.value for k in paths.keys}
    handled = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare) and ast.unparse(n.left) == "axis":
            for c in n.comparators:
                handled |= {c.value} if _str(c) else set(_consts(c) or [])
    return {f"direction_{a}" for a in axes - handled}


# (file relative to engine/, unparsed code expression) -> resolver. Each entry must still match a site.
DYNAMIC_SITES = {
    ("markers.py", "code"): _marker_tuples,
    ("markers.py", "err[0]"): _marker_tuples,
    ("director/adherence.py", "f'direction_{axis}'"): _direction_axes,
}


def scan(sources, dynamic=DYNAMIC_SITES):
    """sources: {relpath: python source}. Returns (emitted {code: {severity}}, unresolved [str], sites used)."""
    found, unresolved, used = {}, [], set()

    def emit(codes, sev, where):
        if sev not in SEVERITIES:
            unresolved.append(f"{where}: severity {sev!r} is not a literal severity")
            return
        for c in codes:
            found.setdefault(c, set()).add(sev)

    for rel, src in sources.items():
        tree = ast.parse(src)
        par = _parents(tree)
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        for call in calls:
            if getattr(call.func, "id", getattr(call.func, "attr", None)) != "Issue":
                continue
            code, sev = _arg(call, 0, "code"), _str(_arg(call, 3, "severity"))
            where = f"{rel}:{call.lineno}"
            if code is None:
                unresolved.append(f"{where}: Issue without a code")
                continue
            if _str(code) is not None:
                emit({code.value}, sev, where)
                continue
            fn = next((f for f in funcs if call in set(ast.walk(f)) and all(
                call not in set(ast.walk(g)) for g in funcs if g is not f and g in set(ast.walk(f)))), None)
            params = [a.arg for a in fn.args.args + fn.args.kwonlyargs] if fn else []
            if isinstance(code, ast.Name) and code.id in params:           # a helper: resolve each call of it
                idx = [a.arg for a in fn.args.args].index(code.id) if code.id in [a.arg for a in fn.args.args] else 99
                sites = [c for c in calls if getattr(c.func, "id", getattr(c.func, "attr", None)) == fn.name]
                if not sites:
                    unresolved.append(f"{where}: helper {fn.name} is never called")
                for c in sites:
                    vals = _values_of(_arg(c, idx, code.id) or ast.Constant(None), c, par)
                    if not vals or not all(isinstance(v, str) for v in vals):
                        unresolved.append(f"{rel}:{c.lineno}: {fn.name}(...) passes a code that is not a literal")
                    else:
                        emit(vals, sev, f"{rel}:{c.lineno}")
                continue
            if isinstance(code, ast.JoinedStr):
                codes = _fstring_codes(code, call, par)
                if codes:
                    emit(codes, sev, where)
                    continue
            key = (rel, ast.unparse(code))
            if key in dynamic:
                used.add(key)
                codes = dynamic[key](tree=tree, fn=fn)
                if not codes:
                    unresolved.append(f"{where}: resolver for {key[1]} found nothing")
                emit(codes, sev, where)
                continue
            unresolved.append(f"{where}: cannot read the code {ast.unparse(code)!r}; add a DYNAMIC_SITES resolver")
    return found, unresolved, used


def _tree():
    return {f.relative_to(ROOT).as_posix(): f.read_text(encoding="utf-8") for f in ROOT.rglob("*.py")
            if "tests" not in f.parts and "__pycache__" not in f.parts}


def registry_problems(found, codes):
    out = [f"unregistered: {c}" for c in sorted(set(found) - set(codes))]
    out += [f"registered but never emitted: {c}" for c in sorted(set(codes) - set(found))]
    out += [f"bad severity: {c}={s}" for c, s in codes.items() if s not in SEVERITIES]
    for c, sevs in found.items():
        if c in codes and codes[c] != max(sevs, key=SEVERITIES.index):
            out.append(f"{c}: registered {codes[c]}, emitted {sorted(sevs)}")
    return out


def test_every_emission_site_is_resolved():
    _, unresolved, used = scan(_tree())
    assert unresolved == []
    assert used == set(DYNAMIC_SITES), f"stale DYNAMIC_SITES entries: {sorted(set(DYNAMIC_SITES) - used)}"


def test_registry_equals_what_the_tree_emits_with_the_emitted_severity():
    found, _, _ = scan(_tree())
    assert registry_problems(found, CODES) == []


def test_dynamic_resolvers_still_see_the_known_codes():
    found, _, _ = scan(_tree())
    for code in ("bad_format", "bad_subject", "direction_world", "direction_opener", "llm_stop_refusal",
                 "llm_stop_max_tokens", "craft_eased", "craft_settled", "craft_lens_28", "craft_deep_focus",
                 "marker_part_mismatch", "seq_shot_count"):
        assert code in found, code
    assert found["craft_eased"] == {"repaired"} and found["seq_shot_count"] == {"error"}


# --- mutation tests: what the old scan let through now fails -----------------------------------------------

HELPER = '''
from engine.issues import Issue
def fix(s, catalog):
    issues = []
    def setp(i, key, value, code):
        issues.append(Issue(code, "p", "m", "repaired"))
    setp(0, "easing", 1, "craft_eased")
    setp(0, "lensMm", 1, "craft_new")
    return issues
'''


def test_a_new_helper_code_must_be_registered():
    found, unresolved, _ = scan({"x.py": HELPER})
    assert unresolved == [] and found["craft_new"] == {"repaired"}
    assert "unregistered: craft_new" in registry_problems(found, CODES)


def test_keyword_issue_calls_are_seen():
    src = 'from engine.issues import Issue\nx = Issue(code="kw_only_code", path="", message="", severity="warning")\n'
    found, unresolved, _ = scan({"x.py": src})
    assert unresolved == [] and found == {"kw_only_code": {"warning"}}


def test_unreadable_emission_sites_fail():
    for src in ('from engine.issues import Issue\ndef f(n):\n    return Issue(make(n), "", "", "error")\n',
                'from engine.issues import Issue\ndef f(a):\n    return Issue(f"x_{a.b}", "", "", "error")\n',
                'from engine.issues import Issue\ndef f(s):\n    return Issue("x_code", "", "", s)\n',
                'from engine.issues import Issue\ndef f():\n    def g(code):\n        return Issue(code, "", "", "info")\n'
                '    return g(pick())\n'):
        assert scan({"x.py": src})[1], src


def test_wrong_registered_severity_fails():
    found, _, _ = scan(_tree())
    assert registry_problems(found, {**CODES, "craft_eased": "error"})
    assert registry_problems(found, {**CODES, "seq_shot_count": "warning"})
    assert registry_problems(found, {k: v for k, v in CODES.items() if k != "craft_settled"})
