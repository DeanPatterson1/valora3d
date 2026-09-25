"""The model's reply is data (spec §3). Parse it, keep only what the model owns, overwrite what the
pipeline owns, merge unsupported asks, snap times to frames, then hand it to the checker."""
import copy
import json
import math

from engine import SCHEMA
from engine.director.capabilities import assumption_lines, merge_llm
from engine.director.output_schema import decompact
from engine.issues import Issue
from engine.markers import _bad_chars
from engine.realism import realism_defaults

LLM_KEYS = ("assumptions", "unsupported", "subject", "world", "lighting", "edit", "effects", "grade", "shots")
OWNED = ("schema", "seed", "direction", "prompt", "format", "markers", "realism")
MAX_LLM_ASSUMPTIONS, MAX_ASSUMPTION_CHARS = 8, 160


def parse_output(text):
    try:
        raw = json.loads(text)
    except (TypeError, ValueError):
        raw = None
    if not isinstance(raw, dict):
        return None, [Issue("llm_not_json", "", "the reply was not one JSON object", "error")]
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
    s["assumptions"] = system + [x for x in llm_lines if x and x not in system][:MAX_LLM_ASSUMPTIONS]
    if isinstance(s.get("subject"), dict):
        s["subject"]["finishOverrides"] = []
        s["subject"].setdefault("motion", {"id": "static", "params": {}})
    fps = job.fmt["fps"]
    for i, sh in enumerate(s.get("shots") if isinstance(s.get("shots"), list) else []):
        if not isinstance(sh, dict):
            continue
        for key in ("startS", "endS"):
            v = sh.get(key)
            if _num(v) and math.isfinite(v * fps):  # NaN/inf/1e308 stay for the checker (bad_shot_times)
                snapped = round(v * fps) / fps
                if abs(snapped - v) > 1e-9:
                    sh[key] = snapped
                    issues.append(Issue("shot_time_snapped", f"shots[{i}].{key}", f"{v} -> {snapped}", "repaired"))
        sh.setdefault("focus", "subject")
        sh.setdefault("transitionIn", "cut")
    for kind, path, ref in _refs(s):
        bid = ref.get("id") if isinstance(ref, dict) else None
        if bid and catalog.get(kind, bid) is not None and bid not in catalog.selectable_ids(kind):
            issues.append(Issue("director_block_forbidden", f"{path}.id",
                                f"{kind} '{bid}' is not on the menu", "error"))
    return s, issues
