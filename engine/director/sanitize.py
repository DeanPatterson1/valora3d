"""The model's reply is data (spec §3). Parse it, keep only what the model owns, overwrite what the
pipeline owns, merge unsupported asks, snap times to frames, then hand it to the checker."""
import copy
import json
import math

from engine import SCHEMA
from engine.clips import in_place_line
from engine.director.capabilities import assumption_lines, clip_line, merge_llm, play_clip_ref, wants_clip
from engine.director.output_schema import decompact
from engine.issues import Issue
from engine.markers import _bad_chars
from engine.realism import realism_defaults

LLM_KEYS = ("assumptions", "unsupported", "subject", "world", "lighting", "edit", "effects", "grade", "shots")
OWNED = ("schema", "seed", "direction", "prompt", "format", "markers", "realism")
MAX_LLM_ASSUMPTIONS, MAX_ASSUMPTION_CHARS = 8, 160
MAX_EFFECTS = 4  # (eng) one per id, a few at most; engine/script.py sets no cap of its own
# Keys the output schema lets the model write (output_schema.scene_output_schema: subject, shot).
SUBJECT_KEYS = ("placement", "motion")
SHOT_KEYS = ("startS", "endS", "purpose", "transitionIn", "focus", "target", "camera")


MAX_DEPTH = 16  # (eng) the output schema nests about 6 deep; anything far deeper is junk or hostile


def _too_deep(x, limit=MAX_DEPTH):
    """Iterative (no recursion), so a hostile 900-deep reply cannot blow the stack in copy/checks."""
    stack = [(x, 1)]
    while stack:
        v, d = stack.pop()
        if isinstance(v, (dict, list)):
            if d > limit:
                return True
            stack.extend((c, d + 1) for c in (v.values() if isinstance(v, dict) else v))
    return False


def parse_output(text):
    try:
        raw = json.loads(text)
    except (TypeError, ValueError, RecursionError):
        raw = None
    if not isinstance(raw, dict):
        return None, [Issue("llm_not_json", "", "the reply was not one JSON object", "error")]
    if _too_deep(raw):
        return None, [Issue("llm_too_deep", "", f"the reply nests deeper than {MAX_DEPTH} levels", "error")]
    return raw, []


def _line(x):
    return "".join(c for c in str(x) if not _bad_chars(c)).strip()[:MAX_ASSUMPTION_CHARS]


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _refs(s):
    """(kind, path, ref) for every block reference in the script."""
    lst = lambda v: v if isinstance(v, list) else []  # noqa: E731
    subj = s.get("subject") if isinstance(s.get("subject"), dict) else {}
    out = [(k, k, s.get(k)) for k in ("world", "lighting", "grade", "edit") if s.get(k) is not None]
    out.append(("motion", "subject.motion", subj.get("motion")))
    out += [("effect", f"effects[{i}]", fx) for i, fx in enumerate(lst(s.get("effects")))]
    out += [("camera", f"shots[{i}].camera", sh.get("camera")) for i, sh in enumerate(lst(s.get("shots")))
            if isinstance(sh, dict)]
    return out


def _drop_unknown(obj, allowed, path, issues):
    for k in [k for k in obj if k not in allowed]:
        del obj[k]
        issues.append(Issue("llm_key_dropped", f"{path}.{k}", "not part of the output schema", "repaired"))


def _cap_effects(effects, issues):
    """One effect per block id, at most MAX_EFFECTS; entries without a string id go to the checker."""
    out, seen = [], set()
    for i, fx in enumerate(effects):
        fid = fx.get("id") if isinstance(fx, dict) else None
        if isinstance(fid, str):
            if fid in seen:
                issues.append(Issue("effect_duplicate_dropped", f"effects[{i}]", f"'{fid}' is already used", "repaired"))
                continue
            seen.add(fid)
        out.append(fx)
    if len(out) > MAX_EFFECTS:
        issues.append(Issue("effects_capped", "effects", f"{len(out)} effects -> the first {MAX_EFFECTS}", "repaired"))
        out = out[:MAX_EFFECTS]
    return out


def sanitize(raw, job, catalog, profile):
    issues = []
    raw = decompact(copy.deepcopy(raw))
    s = {}
    for k, v in raw.items():
        if k in LLM_KEYS:
            s[k] = v
        elif k in OWNED:
            issues.append(Issue("owned_field_overwritten", k, "the system owns this field", "repaired"))
        else:
            issues.append(Issue("llm_key_dropped", k, "not part of the output schema", "repaired"))
    unsup = merge_llm(job.detected, s.pop("unsupported", []), catalog, profile)
    if job.detected:
        issues.append(Issue("unsupported_merged", "unsupported", f"{len(job.detected)} detected ask(s) kept", "repaired"))
    s.update(schema=SCHEMA, seed=job.seed, direction={"id": job.direction.id, "source": job.direction.source},
             prompt=job.prompt, format=dict(job.fmt))
    if job.markers:
        s["markers"] = copy.deepcopy(job.markers)
    if unsup:
        s["unsupported"] = unsup
    realism = realism_defaults(profile, catalog)  # Task 12a: system-added, never model-chosen
    if realism:
        s["realism"] = realism
    llm_lines = [_line(x) for x in (s.get("assumptions") if isinstance(s.get("assumptions"), list) else [])]
    system = job.notes + assumption_lines(unsup)
    own = [x for x in dict.fromkeys(llm_lines) if x and x not in system]  # order kept, repeats dropped
    s["assumptions"] = system + own[:MAX_LLM_ASSUMPTIONS]
    if isinstance(s.get("effects"), list):
        s["effects"] = _cap_effects(s["effects"], issues)
    if isinstance(s.get("subject"), dict):
        _drop_unknown(s["subject"], SUBJECT_KEYS + ("finishOverrides",), "subject", issues)
        s["subject"]["finishOverrides"] = []
        s["subject"].setdefault("motion", {"id": "static", "params": {}})
        motion = s["subject"]["motion"]
        if wants_clip(job.asks, catalog, profile) and (motion.get("id") if isinstance(motion, dict) else None) != "play_clip":
            s["subject"]["motion"] = play_clip_ref(job.asks, profile)
            issues.append(Issue("requested_motion_applied", "subject.motion", "the prompt asked for movement", "repaired"))
            # system lines, then the clip line, then the model's own (the fallback's order)
            s["assumptions"].insert(len(system), clip_line(profile, s["subject"]["motion"]["params"]["clip"]))
        walk = in_place_line(getattr(profile, "animationClips", None) or [], s["subject"]["motion"])
        if walk and not any("plays in place" in x for x in s["assumptions"]):  # a model-chosen root-motion loop
            s["assumptions"].insert(len(system), walk)
    fps = job.fmt["fps"]
    for i, sh in enumerate(s.get("shots") if isinstance(s.get("shots"), list) else []):
        if not isinstance(sh, dict):
            continue
        _drop_unknown(sh, SHOT_KEYS, f"shots[{i}]", issues)
        for key in ("startS", "endS"):
            v = sh.get(key)
            if _num(v) and math.isfinite(v * fps):  # NaN/inf/1e308 stay for the checker (bad_shot_times)
                snapped = round(v * fps) / fps
                if abs(snapped - v) > 1e-9:
                    sh[key] = snapped
                    issues.append(Issue("shot_time_snapped", f"shots[{i}].{key}", f"{v} -> {snapped}", "repaired"))
        sh.setdefault("focus", "subject")
        sh.setdefault("transitionIn", "cut")
    return s, issues + menu_issues(s, catalog)


def menu_issues(s, catalog):
    """director_block_forbidden for every catalog block the script uses that is not on the menu
    (harness-only controls such as turntable). Shared by sanitize and the reroll splice."""
    out = []
    for kind, path, ref in _refs(s):
        bid = ref.get("id") if isinstance(ref, dict) else None
        if isinstance(bid, str) and catalog.get(kind, bid) is not None and bid not in catalog.selectable_ids(kind):
            out.append(Issue("director_block_forbidden", f"{path}.id", f"{kind} '{bid}' is not on the menu", "error"))
    return out
