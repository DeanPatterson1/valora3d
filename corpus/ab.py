"""Own-render A/B pairs (spec §9a): the harness's known-good t3_attempt script with ONE parameter
changed. Records are ground truth from the script; `ab.finding` is written by a person or Claude after
looking at the <= 3 key frames of each variant (Task 10 Step E). Rendering asks the owner first."""
import copy
import json
import re

from corpus import CORPUS_DIR, LOCAL_DIR, ROOT
from engine.craft_rules import primitive

DRAFTS = CORPUS_DIR / "drafts"
BASE = ROOT / "harness" / "suites" / "v0" / "t3_attempt.json"
PAIRS = [
    {"name": "lens-40-vs-85", "model": "pocket_watch", "category": "product", "path": "shots[0].camera.params.lensMm", "a": 40, "b": 85},
    {"name": "rig-softbox-vs-reflection", "model": "pocket_watch", "category": "product", "path": "lighting",
     "a": {"id": "softbox_three_point", "params": {}}, "b": {"id": "reflection_rig", "params": {}}},
    {"name": "haze-0-vs-0p4", "model": "sports_car", "category": "vehicle", "path": "effects",
     "a": [], "b": [{"id": "haze_volume", "params": {"density": 0.4}}]},
    {"name": "tone-grey-vs-black", "model": "sports_car", "category": "vehicle", "path": "world.params.tone", "a": "grey", "b": "black"},
    {"name": "grade-clean-vs-premium", "model": "camera_01", "category": "product", "path": "grade.params.preset", "a": "clean", "b": "premium_dark"},
    {"name": "hero-fstop-2p8-vs-8", "model": "sports_car", "category": "vehicle", "path": "shots[4].camera.params.fstop", "a": 2.8, "b": 8.0},
    {"name": "floorgloss-0-vs-0p8", "model": "vintage_microscope", "category": "product", "path": "world.params.floorGloss", "a": 0.0, "b": 0.8},
    {"name": "separation-1-vs-1p25", "model": "sneaker", "category": "product", "path": "grade.params.separation", "a": 1.0, "b": 1.25},
    {"name": "rim-0p3-vs-2", "model": "mid_century_lounge_chair", "category": "furniture", "path": "lighting",
     "a": {"id": "softbox_three_point", "params": {"rimStrength": 0.3}}, "b": {"id": "softbox_three_point", "params": {"rimStrength": 2.0}}},
    {"name": "hook-height-0p05-vs-0p4", "model": "mid_century_lounge_chair", "category": "furniture", "path": "shots[0].camera.params.heightFrac", "a": 0.05, "b": 0.4},
]
_STEP = re.compile(r"([A-Za-z]+)(?:\[(\d+)\])?")
_MOVE = {"dolly": "push", "dolly_in": "push", "truck": "slide", "arc": "arc", "orbit": "orbit", "static": "locked"}


def set_path(obj, path, value):
    steps = [_STEP.fullmatch(p).groups() for p in path.split(".")]
    cur = obj
    for i, (key, idx) in enumerate(steps):
        last = i == len(steps) - 1
        if idx is None:
            if last:
                cur[key] = copy.deepcopy(value)
            else:
                cur = cur.setdefault(key, {})
        else:
            if last:
                cur[key][int(idx)] = copy.deepcopy(value)
            else:
                cur = cur[key][int(idx)]


def scripts_for(pair):
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base["direction"] = {"id": f"ab/{pair['name']}", "source": "ab"}
    a, b = copy.deepcopy(base), copy.deepcopy(base)
    set_path(a, pair["path"], pair["a"])
    set_path(b, pair["path"], pair["b"])
    return a, b


def _lens(ref, cam):
    if cam["framing"] == "detail":
        return "macro"
    mm = ref["params"].get("lensMm", cam["params"]["lensMm"]["default"])
    return "ultrawide" if mm < 24 else "wide" if mm < 40 else "normal" if mm < 70 else "tele"


def record_for(pair, catalog):
    a, _ = scripts_for(pair)
    shots = []
    for sh in a["shots"]:
        cam = catalog.get("camera", sh["camera"]["id"])
        fstop = sh["camera"]["params"].get("fstop", cam["params"]["fstop"]["default"])
        shots.append({"startS": sh["startS"], "endS": sh["endS"],
                      "cameraMove": _MOVE.get(primitive(sh, catalog), "other"),
                      "lensClass": _lens(sh["camera"], cam),
                      "cameraHeight": "low" if sh["camera"]["id"] == "low_hero_push" else "eye",
                      "dutchTilt": False, "focus": "shallow" if fstop <= 4 else "deep",
                      "subjectMotion": "static", "renderPass": "final", "notes": ""})
    return {
        "schema": "valora.ref/1", "id": f"ab-{pair['name']}",
        "source": {"kind": "own_render", "script": f"corpus/ab.py#{pair['name']}", "downloaded": False,
                   "selection": "hand", "studiedAt": "pending"},
        "method": "script_ground_truth", "qualityEstimate": None,
        "subject": {"category": pair["category"], "sizeClass": "vehicle" if pair["category"] == "vehicle" else "hand",
                    "description": f"eval model {pair['model']}"},
        "format": {"aspect": a["format"]["aspect"], "durationS": a["format"]["durationS"], "fps": a["format"]["fps"],
                   "shotCount": len(shots), "cutTimesS": [s["startS"] for s in shots[1:]]},
        "layout": {"kind": "full", "contentAspect": a["format"]["aspect"]},
        "shots": shots,
        "world": {"type": "cyclorama", "timeOfDay": "studio", "weather": "n/a",
                  "atmosphere": ["haze"] if a.get("effects") else []},
        "lighting": {"setup": [a["lighting"]["id"]], "keyDirection": "rig", "colorTemps": "rig", "practicals": False},
        "grade": {"dominantHues": [], "contrast": "mid", "saturation": "mid", "bloom": None, "halation": None,
                  "grain": False, "vignette": None},
        "effects": [fx["id"] for fx in a.get("effects", [])], "simulation": [], "surfaceState": [],
        "secondarySubjects": [], "overlays": [], "transitions": [{"atS": s["startS"], "kind": "cut"} for s in shots[1:]],
        "cameraImperfections": {k: "no" for k in ("motionBlur", "focusBreathing", "exposureAdaptation", "rollingShutter",
                                                  "sensorNoise", "microShake", "lensFlare", "lensDistortion",
                                                  "chromaticAberration")} | {"motionBlur": "yes"},
        "pacing": {"energy": "medium", "musicSyncCuts": None},
        "neverThoughtOf": [], "evidence": {"script": [f"corpus/ab.py#{pair['name']}"]},
        "confidence": {"overall": "high", "uncertainFields": []},
        "ab": {"pair": pair["name"], "param": pair["path"], "a": pair["a"], "b": pair["b"], "frames": [], "finding": None},
    }


def render(pair, key_limit=3, tier="keyframes"):
    """Owner-gated: <= 3 key frames per variant, keyframes tier. Returns the two output dirs."""
    from engine.catalog import Catalog
    from engine.compiler.run import compile_scene
    from engine.profile import SubjectProfile
    prof = SubjectProfile.from_dict(json.loads((ROOT / "engine/tests/fixtures/profiles" / f"{pair['model']}.json")
                                               .read_text(encoding="utf-8")))
    glb = ROOT / "assets-in" / "models" / pair["model"] / f"{pair['model']}.glb"
    outs = []
    for tag, s in zip("ab", scripts_for(pair)):
        out = LOCAL_DIR / "ab" / pair["name"] / tag
        compile_scene(s, prof, glb, out, tier=tier, frames="key", key_limit=key_limit, catalog=Catalog.load())
        outs.append(out)
    return outs


def by_name(name):
    for p in PAIRS:
        if p["name"] == name:
            return p
    raise SystemExit(f"no A/B pair {name!r}; see py -m corpus ab list")


def write_draft(pair, catalog):
    DRAFTS.mkdir(parents=True, exist_ok=True)
    rec = record_for(pair, catalog)
    out = DRAFTS / f"{rec['id']}.json"
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
