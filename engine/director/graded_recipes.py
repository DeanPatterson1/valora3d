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


_CACHE = {}


def cached():
    """load() once per process (the dice ask per candidate); callers must not mutate it."""
    if "recipes" not in _CACHE:
        _CACHE["recipes"] = load()
    return _CACHE["recipes"]


def refs(r):
    """(kind, block ref) for every block a recipe uses."""
    out = [("world", r["world"]), ("lighting", r["lighting"]), ("grade", r["grade"])]
    out += [("effect", e) for e in r["effects"]] + [("camera", sh["camera"]) for sh in r["shots"]]
    if r.get("edit"):
        out.append(("edit", r["edit"]))
    return out


def usable(world_id, catalog):
    """The recipe for this world when this catalog can play it, else None. Every block must exist, and a growth block
    (catalog_growth.json) must also be on the catalog's menu, so the site catalog (ungraded growth blocks off) never
    replays one. practicals_only is graded but never director-selectable (a harness-set lighting) and not a growth
    block, so it needs only to exist."""
    r = cached().get(world_id)
    if r is None or world_id not in catalog.selectable_ids("world"):
        return None
    if "growth" not in _CACHE:
        from engine.director.site import load_growth
        _CACHE["growth"] = load_growth()["blocks"]
    growth = _CACHE["growth"]
    ok = all(catalog.get(k, x["id"]) is not None and (f"{k}/{x['id']}" not in growth
                                                        or x["id"] in catalog.selectable_ids(k))
             for k, x in refs(r))
    return r if ok else None


def direction_axes(r):
    """The direction axes a recipe IS (mood = its grade preset, pace = its edit pace, opener = its first camera,
    weather from its effects, still air: the site's own wind). The dice roll exactly this for a graded world unless a
    prompt pins an axis, so the direction id, the adherence checks and replays all describe the graded look."""
    ids = {e["id"] for e in r["effects"]}
    return {"mood": r["grade"]["params"]["preset"],
            "pace": ((r.get("edit") or {}).get("params") or {}).get("pace", "medium"),
            "opener": r["shots"][0]["camera"]["id"],
            "weather": "rain" if "rain" in ids else "wet" if "wet_surface" in ids else "dry",
            "wind": "calm"}


def graded_axes(world_id, catalog):
    """direction_axes of this world's usable recipe, or None (the dice roll this world freely)."""
    r = usable(world_id, catalog)
    return direction_axes(r) if r else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    a = ap.parse_args(argv)
    DATA.write_text(json.dumps(extract(a.root), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {DATA}")


if __name__ == "__main__":
    main()
