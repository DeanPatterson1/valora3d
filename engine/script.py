"""Structural validation and in-place-safe repair of a valora.scene/1 script (spec §4.2, §4.6)."""
import copy
import math
from engine import SCHEMA
from engine.catalog import ASPECTS, KINDS, clamp_number
from engine.issues import Issue
from engine.markers import _ID as _MARKER_ID
from engine.markers import validate_shapes as _marker_shapes

FPS = (24, 25, 30, 60)
DURATION_RANGE = (3, 30)
SNAP_GAP_S = 0.05
SNAP_END_S = 0.25
FRAME_TOL = 1e-6        # shot boundaries: |t * fps - round(t * fps)| (frames)
MIN_SHOT_FRAMES = 2
RESERVED = ("audio",)
PURPOSES = ("hook", "establish", "detail", "motion", "hero", "packshot")
TRANSITIONS = ("cut",)
# Reserved: named in the craft research, rejected until their edit blocks exist (CATALOG-GAPS rank 8).
TRANSITIONS_RESERVED = ("flash", "dark_tunnel", "focus_handoff", "black_card", "whip", "hidden_cut",
                        "mask_wipe")


def _num(v):
    """A finite int/float that is not a bool. Ints too large for a float count as non-finite."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:
        return False


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
            if not _num(v):
                params[k] = spec["default"]
                issues.append(Issue("param_bad_type", p, f"{v!r} is not a finite number; used default", "repaired"))
            elif clamp_number(spec, v) != v:
                params[k] = clamp_number(spec, v)
                issues.append(Issue("param_clamped", p, f"clamped {v} to {params[k]}", "repaired"))
        elif spec["type"] == "enum" and v not in spec["values"]:
            params[k] = spec["default"]
            issues.append(Issue("param_bad_enum", p, f"{v!r} not in {spec['values']}; used default", "repaired"))
        elif spec["type"] == "bool" and not isinstance(v, bool):
            params[k] = spec["default"]
            issues.append(Issue("param_bad_type", p, f"{v!r} is not a bool; used default", "repaired"))


def _block(ref, kind, path, catalog, issues):
    if (not isinstance(ref, dict) or not isinstance(ref.get("id"), str)
            or not isinstance(ref.get("params", {}), dict)):
        issues.append(Issue("bad_block_ref", path, "expected {id: string, params: object}", "error"))
        return None
    m = catalog.get(kind, ref["id"])
    if m is None:
        issues.append(Issue("unknown_block", f"{path}.id", f"no {kind} '{ref['id']}' in catalog", "error"))
        return None
    _repair_params(ref, m, path, issues)
    return m


def _valid_target(t):
    if not isinstance(t, dict) or len(t) != 1:
        return False
    if "marker" in t:
        return isinstance(t["marker"], str) and bool(_MARKER_ID.match(t["marker"]))
    d = t.get("detail")
    return isinstance(d, int) and not isinstance(d, bool) and d >= 0


def _shot_fields(i, sh, issues):
    p = f"shots[{i}]"
    if "purpose" in sh and sh["purpose"] not in PURPOSES:
        issues.append(Issue("bad_purpose", f"{p}.purpose", f"must be one of {PURPOSES}", "error"))
    tr = sh.get("transitionIn", "cut")
    if tr in TRANSITIONS_RESERVED:
        issues.append(Issue("transition_not_available", f"{p}.transitionIn",
                            f"'{tr}' is reserved; only {TRANSITIONS} exist in this version", "error"))
    elif tr not in TRANSITIONS:
        issues.append(Issue("bad_transition", f"{p}.transitionIn", f"must be one of {TRANSITIONS}", "error"))
    if "surfaceState" in sh:   # one ground state per clip until a transition block exists (phase 5 Task 57)
        issues.append(Issue("surface_state_continuity", f"{p}.surfaceState",
                            "the ground's wet/dry state is set once per clip, not per shot", "error"))
    if "target" in sh and not _valid_target(sh["target"]):
        issues.append(Issue("bad_target", f"{p}.target", "expected {marker: id} or {detail: index >= 0}", "error"))


def _valid_fps(fps):
    return isinstance(fps, int) and not isinstance(fps, bool) and fps in FPS


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
    if _num(dur) and last["endS"] != dur:
        if abs(last["endS"] - dur) <= SNAP_END_S:
            last["endS"] = dur
            issues.append(Issue("shot_snapped", f"shots[{len(shots) - 1}].endS", f"snapped to {dur}", "repaired"))
        else:
            issues.append(Issue("shots_not_contiguous", f"shots[{len(shots) - 1}].endS", f"last shot ends {last['endS']}, clip is {dur}", "error"))
    fps = s["format"].get("fps")
    for i, sh in enumerate(shots):
        if not sh["startS"] < sh["endS"]:
            issues.append(Issue("bad_shot_times", f"shots[{i}]", "startS must be < endS", "error"))
            continue
        if not _valid_fps(fps):
            continue  # bad_fps is reported by the caller
        # The compiler cuts in the closed-shutter gap between two whole frames, so every boundary
        # must be a whole frame; a shot needs two frames for its path to have a velocity.
        for key in ("startS", "endS"):
            f = sh[key] * fps
            if abs(f - round(f)) > FRAME_TOL:
                issues.append(Issue("shot_not_frame_aligned", f"shots[{i}].{key}",
                                    f"{sh[key]} s is {f:.4f} frames at {fps} fps; must be a whole frame", "error"))
        if round(sh["endS"] * fps) - round(sh["startS"] * fps) < MIN_SHOT_FRAMES:
            issues.append(Issue("shot_too_short", f"shots[{i}]",
                                f"shorter than {MIN_SHOT_FRAMES} frames at {fps} fps", "error"))


MAX_UNSUPPORTED = 12
_UNSUPPORTED_KEYS = {"ask": 60, "capability": 40, "note": 160, "source": 40}  # key -> max length


def _unsupported_ok(v):
    return isinstance(v, list) and len(v) <= MAX_UNSUPPORTED and all(
        isinstance(u, dict) and set(u) == set(_UNSUPPORTED_KEYS)
        and all(isinstance(u[k], str) and 0 < len(u[k]) <= n for k, n in _UNSUPPORTED_KEYS.items())
        for u in v)


def validate_and_repair(script, catalog):
    """Return (repaired_copy, issues). Never mutates the input."""
    s = copy.deepcopy(script)
    if not isinstance(s, dict):
        return s, [Issue("bad_script", "", "script must be a JSON object", "error")]
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
    shots = s.get("shots") if isinstance(s.get("shots"), list) else []  # non-list: no_shots in _shots
    effects = s.get("effects", [])
    if not isinstance(effects, list):
        issues.append(Issue("bad_effects", "effects", "'effects' must be a list", "error"))
        effects = []
    for i, sh in enumerate(shots):
        if isinstance(sh, dict) and not isinstance(sh.get("camera"), dict):
            sh["camera"] = None
    fmt = s["format"]
    if fmt.get("aspect") not in ASPECTS:
        issues.append(Issue("bad_aspect", "format.aspect", f"must be one of {ASPECTS}", "error"))
    d = fmt.get("durationS")
    if not _num(d) or not DURATION_RANGE[0] <= d <= DURATION_RANGE[1]:
        issues.append(Issue("bad_duration", "format.durationS", f"must be in {DURATION_RANGE}", "error"))
    if not _valid_fps(fmt.get("fps")):
        issues.append(Issue("bad_fps", "format.fps", f"must be one of {FPS}", "error"))
    if "markers" in s:
        _marker_shapes(s["markers"], fmt.get("durationS"), issues)
    if "unsupported" in s and not _unsupported_ok(s["unsupported"]):
        issues.append(Issue("bad_unsupported", "unsupported",
                            f"a list of <= {MAX_UNSUPPORTED} {{ask, capability, note, source}} strings", "error"))
    subj = s["subject"]
    if subj.get("placement") not in ("ground", "float"):
        issues.append(Issue("bad_placement", "subject.placement", "ground or float", "error"))
    _block(subj.get("motion"), "motion", "subject.motion", catalog, issues)
    _block(s.get("world"), "world", "world", catalog, issues)
    _block(s.get("lighting"), "lighting", "lighting", catalog, issues)
    _block(s.get("grade"), "grade", "grade", catalog, issues)
    if s.get("edit") is not None:
        _block(s.get("edit"), "edit", "edit", catalog, issues)
    for i, fx in enumerate(effects):
        _block(fx, "effect", f"effects[{i}]", catalog, issues)
    if s.get("wind") is not None:
        _block(s.get("wind"), "field", "wind", catalog, issues)   # system-owned; reuses existing codes
    realism = s.get("realism", [])
    if not isinstance(realism, list):
        issues.append(Issue("bad_realism", "realism", "'realism' must be a list", "error"))
        realism = []
    for i, ref in enumerate(realism):
        kind = ref.get("kind") if isinstance(ref, dict) else None
        if kind == "realism":   # system-owned; engine/physics/applies.py resolves ids and pins (info only)
            if not isinstance(ref.get("id"), str) or not isinstance(ref.get("params", {}), dict):
                issues.append(Issue("bad_realism", f"realism[{i}]", "expected {kind, id, params}", "error"))
            continue
        m = _block(ref, kind, f"realism[{i}]", catalog, issues) if kind in KINDS else None
        if kind not in KINDS:
            issues.append(Issue("bad_realism", f"realism[{i}].kind", f"kind must be one of {KINDS}", "error"))
        elif m is not None and not (kind == "realism" or m.get("alwaysOn")):
            issues.append(Issue("realism_not_always_on", f"realism[{i}].id",
                                f"{ref['id']} is not an always-on block", "error"))
    for i, sh in enumerate(shots):
        if not isinstance(sh, dict):
            continue  # reported by _shots
        _block(sh.get("camera"), "camera", f"shots[{i}].camera", catalog, issues)
        _shot_fields(i, sh, issues)
        if sh.get("focus", "subject") != "subject":
            issues.append(Issue("bad_focus", f"shots[{i}].focus", "v1 supports focus 'subject' only", "error"))
    _shots(s, issues)
    return s, issues
