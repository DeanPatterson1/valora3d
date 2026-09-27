"""py -m harness.realism_round --round r10 [--shots court,field_golden,street_night,rear] [--prev r9]
                               [--prev-for court=r9z] [--tier final] [--sheets-only] [--dry-run]

The realism round driver (rounds 7-9 ran it from a scratch file; round 10 commits it). Each shot renders the
committed script under harness/realism/ against the black sports car (#0b0b0c gloss, the committed profile)
into harness/out/look/real_<round>_<shot>/, with the director's premium look applied the way a real job gets it:
the hook's distance re-solved by the premium hero (silhouette width) with the script's own lens / height /
f-stop kept, and a wet ground given the premium pool. Then the side-by-side sheets
harness/out/look/real_<round>_sbs/<sheet>.png: reference | previous round | this round, 960 px tall.

Renders run one shot after another (one Blender at a time). --dry-run prints the plan and renders nothing."""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "harness" / "realism"
LOOK = ROOT / "harness" / "out" / "look"
REFS = ROOT / "harness" / "out" / "refs" / "video_refs"
GLB = ROOT / "assets-in" / "models" / "sports_car" / "sports_car.glb"
PAINT = {"color": "#0b0b0c", "finish": "gloss"}
SHEET_H = 960

# shot -> (script under harness/realism, frames to render)
SHOTS = {
    "court": ("court.json", [30, 83, 128]),
    "field_golden": ("field_golden.json", [30]),
    "street_night": ("street_night.json", [30]),
    "rear": ("rear.json", [83]),
}
# sheet -> (reference image under video_refs, its label, shot, frame, engine label suffix). Each reference is the
# video frame whose camera best matches the engine shot (same end of the car, height and framing; environment second),
# cut from the source videos into picks/ (2026-09-27; candidates/ holds the 4 fps browse sheets).
SHEETS = {
    "hero": ("picks/hero_v01_12.0s_front34_low_street.png",
             "reference v01 12.0s (low front 3/4, street; blue car, rotated + cropped)", "court", 30, ""),
    "wheel": ("picks/wheel_v04_7.3s_side_low_wet.png",
              "reference v04 7.3s (low side wheel, wet; crop)", "court", 83, ""),
    "headlight": ("picks/headlight_v04_9.3s_front34_lamp.png",
                  "reference v04 9.3s (front 3/4 headlight, rain; crop)", "court", 128, ""),
    "field_golden": ("picks/field_golden_v11_11.75s_front34_low_grass.png",
                     "reference v11 11.75s (low front 3/4, car in grass)", "field_golden", 30, ""),
    "street_night": ("picks/street_night_v03_11.8s_front_headlights_night.png",
                     "reference v03 11.8s (front, headlights on, night tunnel; higher camera)", "street_night", 30, ""),
    "rain_closeup": ("picks/rain_closeup_v04_7.3s_rear_quarter_low_rain.png",
                     "reference v04 7.3s (low rear quarter, rain)", "rear", 83, " (rear quarter, 85 mm f/2.8)"),
}


def shot_dir(rnd, shot):
    return LOOK / f"real_{rnd}_{shot}"


def frame_png(rnd, shot, frame):
    return shot_dir(rnd, shot) / "beauty" / f"{frame:04d}.png"


def load_script(shot):
    return json.loads((HERE / SHOTS[shot][0]).read_text(encoding="utf-8"))


def load_profile():
    from engine.profile import SubjectProfile
    return SubjectProfile.from_dict(json.loads((HERE / "sports_car_profile.json").read_text(encoding="utf-8")))


class _Replay:
    """A stub rng for _premium_hero: replays the script's own height and lens instead of drawing new ones."""

    def __init__(self, vals):
        self.vals = list(vals)

    def uniform(self, a, b):
        return self.vals.pop(0)


def premium(script, prof, cat):
    """The director's premium look on a hand script (in place): the hook's distance re-solved by the premium hero
    with lens / height / f-stop kept; a wet ground gets the premium pool. Returns a one-line summary."""
    from engine.checker import check
    from engine.director.fallback import PREMIUM_POOL, _premium_hero, _width_frac
    from engine.occluders import declared
    sh = script["shots"][0]
    prm = sh["camera"]["params"]
    keep = dict(prm)
    boxes = declared(cat.get("world", script["world"]["id"]), prof)
    for e in script.get("effects", []):
        if e["id"] == "wet_surface":
            e["params"].setdefault("pool", PREMIUM_POOL)
    _premium_hero(sh, 0.0, _Replay([prm["heightFrac"] * prof.sizeM[2], prm["lensMm"]]), prof, cat,
                  script["format"]["aspect"], boxes)
    prm["fstop"], prm["lensMm"] = keep["fstop"], keep["lensMm"]
    r = check(copy.deepcopy(script), prof, cat)
    q = {**{k: v["default"] for k, v in cat.get("camera", sh["camera"]["id"])["params"].items()},
         **r.script["shots"][0]["camera"]["params"]}
    wf = _width_frac(cat.load_camera_path(sh["camera"]["id"]), q, prof, script["format"]["aspect"], 0.0)
    return {"distance": [keep.get("distance"), prm["distance"]], "silhouetteWidth": round(wf or -1, 3), "ok": r.ok}


def plan(rnd, shots, prev):
    return {"round": rnd, "prev": prev,
            "shots": {s: {"script": str(HERE / SHOTS[s][0]), "frames": SHOTS[s][1], "out": str(shot_dir(rnd, s))}
                      for s in shots},
            "sheets": {n: str(LOOK / f"real_{rnd}_sbs" / f"{n}.png") for n in SHEETS}}


def render_shot(rnd, shot, tier="final"):
    from engine.catalog import Catalog
    from engine.compiler.run import compile_scene
    cat = Catalog.load()
    prof = load_profile()
    script = load_script(shot)
    hook = premium(script, prof, cat)
    print(shot, "hook", json.dumps(hook), flush=True)
    t = time.time()
    res = compile_scene(copy.deepcopy(script), prof, GLB, shot_dir(rnd, shot), tier=tier, frames=SHOTS[shot][1],
                        paint=PAINT)
    print(shot, "done", round(time.time() - t), json.dumps(res.get("renderLog"))[:300], flush=True)
    return res


def _panel(path, label):
    from PIL import Image
    if not Path(path).exists():
        im = Image.new("RGB", (540, SHEET_H), (40, 40, 40))
        return im, label + " (missing)"
    im = Image.open(path).convert("RGB")
    return im.resize((int(im.width * SHEET_H / im.height), SHEET_H), Image.LANCZOS), label


def build_sheets(rnd, prev, prev_for=None):
    """prev_for: {shot: round} overrides the middle panel's round per shot (e.g. court=r9z, a re-render of the
    previous round's court at a later HEAD)."""
    prev_for = prev_for or {}
    from PIL import Image, ImageDraw
    out_dir = LOOK / f"real_{rnd}_sbs"
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for name, (ref, ref_label, shot, frame, suffix) in SHEETS.items():
        panels = [_panel(REFS / ref, ref_label)]
        pv = prev_for.get(shot, prev)
        if pv:
            panels.append(_panel(frame_png(pv, shot, frame), f"engine {pv}{suffix}"))
        panels.append(_panel(frame_png(rnd, shot, frame), f"engine {rnd}{suffix}"))
        c = Image.new("RGB", (sum(p.width for p, _ in panels) + 12 * (len(panels) - 1), SHEET_H + 28), (20, 20, 20))
        d = ImageDraw.Draw(c)
        x = 0
        for im, lab in panels:
            c.paste(im, (x, 28))
            d.text((x + 6, 6), lab, fill=(230, 230, 230))
            x += im.width + 12
        c.save(out_dir / f"{name}.png")
        made.append(str(out_dir / f"{name}.png"))
    return made


def main(argv=None):
    ap = argparse.ArgumentParser(prog="harness.realism_round")
    ap.add_argument("--round", required=True, help="round name, e.g. r10 (outputs real_<round>_<shot>)")
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--prev", help="previous round for the middle sheet panel, e.g. r9")
    ap.add_argument("--prev-for", help="per-shot previous round, e.g. court=r9z,rear=r9z")
    ap.add_argument("--tier", default="final")
    ap.add_argument("--sheets-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    shots = [s.strip() for s in a.shots.split(",") if s.strip()]
    unknown = [s for s in shots if s not in SHOTS]
    if unknown:
        ap.error(f"unknown shot(s) {unknown}; known: {sorted(SHOTS)}")
    if a.dry_run:
        print(json.dumps(plan(a.round, shots, a.prev), indent=1))
        return 0
    if not a.sheets_only:
        for s in shots:                     # serial: one Blender at a time
            render_shot(a.round, s, a.tier)
    prev_for = dict(kv.split("=", 1) for kv in (a.prev_for or "").split(",") if "=" in kv)
    for p in build_sheets(a.round, a.prev, prev_for):
        print("sheet", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
