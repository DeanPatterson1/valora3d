"""Structural validation and in-place-safe repair of a valora.scene/1 script (spec §4.2, §4.6)."""
import copy
from engine import SCHEMA
from engine.catalog import ASPECTS
from engine.issues import Issue

FPS = (24, 25, 30, 60)
DURATION_RANGE = (3, 30)
SNAP_GAP_S = 0.05
SNAP_END_S = 0.25
RESERVED = ("audio",)


def _repair_params(ref, manifest, path, issues):
    specs = manifest["params"]
    params = ref.setdefault("params", {})
    for k in [k for k in params if k not in specs]:
        del params[k]
        issues.append(Issue("param_unknown_dropped", f"{path}.params.{k}", f"'{k}' is not a param of {manifest['id']}", "repaired"))
    for k, spec in specs.items():
        p = f"{path}.params.{k}"
        if k not in params:
            params[k] = spec["default"]
            issues.append(Issue("param_default", p, f"filled default {spec['default']!r}", "repaired"))
            continue
        v = params[k]
        if spec["type"] == "number":
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                params[k] = spec["default"]
                issues.append(Issue("param_bad_type", p, f"{v!r} is not a number; used default", "repaired"))
            elif not spec["min"] <= v <= spec["max"]:
                params[k] = float(min(max(v, spec["min"]), spec["max"]))
                issues.append(Issue("param_clamped", p, f"clamped {v} to {params[k]}", "repaired"))
        elif spec["type"] == "enum" and v not in spec["values"]:
            params[k] = spec["default"]
            issues.append(Issue("param_bad_enum", p, f"{v!r} not in {spec['values']}; used default", "repaired"))
        elif spec["type"] == "bool" and not isinstance(v, bool):
            params[k] = spec["default"]
            issues.append(Issue("param_bad_type", p, f"{v!r} is not a bool; used default", "repaired"))


def _block(ref, kind, path, catalog, issues):
    if not isinstance(ref, dict) or "id" not in ref:
        issues.append(Issue("bad_block_ref", path, "expected {id, params}", "error"))
        return None
    m = catalog.get(kind, ref["id"])
    if m is None:
        issues.append(Issue("unknown_block", f"{path}.id", f"no {kind} '{ref['id']}' in catalog", "error"))
        return None
    _repair_params(ref, m, path, issues)
    return m


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _shots(s, issues):
    shots = s.get("shots") or []
    if not isinstance(shots, list) or not shots:
        issues.append(Issue("no_shots", "shots", "at least one shot required", "error"))
        return
    bad = [i for i, sh in enumerate(shots)
           if not isinstance(sh, dict) or not _num(sh.get("startS")) or not _num(sh.get("endS"))]
    if bad:
        for i in bad:
            issues.append(Issue("bad_shot_times", f"shots[{i}]", "startS and endS must be numbers", "error"))
        return
    dur = s["format"].get("durationS")
    if shots[0]["startS"] != 0:
        if abs(shots[0]["startS"]) <= SNAP_GAP_S:
            shots[0]["startS"] = 0
            issues.append(Issue("shot_snapped", "shots[0].startS", "snapped to 0", "repaired"))
        else:
            issues.append(Issue("shots_not_contiguous", "shots[0].startS", "first shot must start at 0", "error"))
    for i in range(1, len(shots)):
        prev_end, start = shots[i - 1]["endS"], shots[i]["startS"]
        if start != prev_end:
            if abs(start - prev_end) <= SNAP_GAP_S:
                shots[i]["startS"] = prev_end
                issues.append(Issue("shot_snapped", f"shots[{i}].startS", f"snapped {start} to {prev_end}", "repaired"))
            else:
                issues.append(Issue("shots_not_contiguous", f"shots[{i}].startS", f"gap/overlap {start} vs {prev_end}", "error"))
    last = shots[-1]
    if isinstance(dur, (int, float)) and last["endS"] != dur:
        if abs(last["endS"] - dur) <= SNAP_END_S:
            last["endS"] = dur
            issues.append(Issue("shot_snapped", f"shots[{len(shots) - 1}].endS", f"snapped to {dur}", "repaired"))
        else:
            issues.append(Issue("shots_not_contiguous", f"shots[{len(shots) - 1}].endS", f"last shot ends {last['endS']}, clip is {dur}", "error"))
    for i, sh in enumerate(shots):
        if not sh["startS"] < sh["endS"]:
            issues.append(Issue("bad_shot_times", f"shots[{i}]", "startS must be < endS", "error"))


def validate_and_repair(script, catalog):
    """Return (repaired_copy, issues). Never mutates the input."""
    s = copy.deepcopy(script)
    issues = []
    if s.get("schema") != SCHEMA:
        issues.append(Issue("bad_schema", "schema", f"expected {SCHEMA}", "error"))
    if not isinstance(s.get("seed"), int) or isinstance(s["seed"], bool) or s["seed"] < 0:
        issues.append(Issue("bad_seed", "seed", "seed must be a non-negative integer", "error"))
    for key in RESERVED:
        if key in s:
            issues.append(Issue("reserved_not_in_v1", key, f"'{key}' is reserved and not supported in v1", "error"))
    # The director is an LLM: malformed shapes must become errors, never crashes.
    for key in ("format", "subject"):
        if not isinstance(s.get(key), dict):
            issues.append(Issue(f"bad_{key}", key, f"'{key}' must be an object", "error"))
            s[key] = {}
    for i, sh in enumerate(s.get("shots") or []):
        if isinstance(sh, dict) and not isinstance(sh.get("camera"), dict):
            sh["camera"] = None
    fmt = s["format"]
    if fmt.get("aspect") not in ASPECTS:
        issues.append(Issue("bad_aspect", "format.aspect", f"must be one of {ASPECTS}", "error"))
    d = fmt.get("durationS")
    if not isinstance(d, (int, float)) or not DURATION_RANGE[0] <= d <= DURATION_RANGE[1]:
        issues.append(Issue("bad_duration", "format.durationS", f"must be in {DURATION_RANGE}", "error"))
    if fmt.get("fps") not in FPS:
        issues.append(Issue("bad_fps", "format.fps", f"must be one of {FPS}", "error"))
    subj = s["subject"]
    if subj.get("placement") not in ("ground", "float"):
        issues.append(Issue("bad_placement", "subject.placement", "ground or float", "error"))
    _block(subj.get("motion"), "motion", "subject.motion", catalog, issues)
    _block(s.get("world"), "world", "world", catalog, issues)
    _block(s.get("lighting"), "lighting", "lighting", catalog, issues)
    _block(s.get("grade"), "grade", "grade", catalog, issues)
    for i, fx in enumerate(s.get("effects", [])):
        _block(fx, "effect", f"effects[{i}]", catalog, issues)
    for i, sh in enumerate(s.get("shots") or []):
        if not isinstance(sh, dict):
            continue  # reported by _shots
        _block(sh.get("camera"), "camera", f"shots[{i}].camera", catalog, issues)
        if sh.get("focus", "subject") != "subject":
            issues.append(Issue("bad_focus", f"shots[{i}].focus", "v1 supports focus 'subject' only", "error"))
    _shots(s, issues)
    return s, issues
