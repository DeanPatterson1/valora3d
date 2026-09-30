"""The owner-graded look recipes, extracted from the graded harness scripts (never hand-copied).

Customer jobs (no LLM key) run the fallback director. Its dice-rolled lighting, grade and camera choices did not
reproduce what the owner graded ("all good now", 2026-09-27: realism round 16 courtyard and night street, round 15
golden field), so customer renders looked worse than the graded stills. engine/director/graded_recipes.json holds,
per graded world, the parts of those scripts that make the LOOK: world (+params), lighting (+params), effects, grade
(+params), the edit pace and the shot list (times, purposes, cameras, detail targets). engine/director/graded.py
replays them for any subject. Not copied: the wind (the site's gradedWind, pinned by the physics layer), the
realism list (profile-dependent, realism_defaults) and the subject block.

Regenerate after the owner grades a new world:  py -m engine.director.graded_recipes [--root <checkout>]
(the sources live under harness/out/look/ of the main checkout, which is not tracked); a test re-extracts and
compares whenever the sources are present."""
import argparse
import copy
import json
from pathlib import Path

SCHEMA = "valora.graded_recipes/1"
DATA = Path(__file__).with_name("graded_recipes.json")
# the graded scripts' job files, repo-relative (the world id of each is read FROM the script, not typed here)
SOURCES = ("harness/out/look/real_r16_court/job.json",
           "harness/out/look/real_r15_field_golden/job.json",
           "harness/out/look/real_r16_street_night/job.json")
DEFAULT_ROOT = Path("C:/Users/deand/Projects/Rendering")
SHOT_KEYS = ("purpose", "focus", "camera", "target")


def recipe_of(script, source):
    """One world's recipe from a graded script (deep-copied so the source is never aliased)."""
    d = script["format"]["durationS"]
    shots = []
    for sh in script["shots"]:
        e = {"lengthS": round(sh["endS"] - sh["startS"], 4)}
        e.update({k: copy.deepcopy(sh[k]) for k in SHOT_KEYS if k in sh})
        shots.append(e)
    return {"source": source, "durationS": d, "aspect": script["format"]["aspect"],
            "world": copy.deepcopy(script["world"]), "lighting": copy.deepcopy(script["lighting"]),
            "effects": copy.deepcopy(script.get("effects", [])), "grade": copy.deepcopy(script["grade"]),
            "edit": copy.deepcopy(script.get("edit")), "shots": shots}


def extract(root=DEFAULT_ROOT, sources=SOURCES):
    out = {}
    for rel in sources:
        script = json.loads((Path(root) / rel).read_text(encoding="utf-8"))["script"]
        out[script["world"]["id"]] = recipe_of(script, rel)
    return {"schema": SCHEMA, "worlds": dict(sorted(out.items()))}


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))["worlds"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    a = ap.parse_args(argv)
    DATA.write_text(json.dumps(extract(a.root), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {DATA}")


if __name__ == "__main__":
    main()
