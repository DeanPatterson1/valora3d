"""One-off (2026-09-25): bring the 11 pilot records to the full valora.ref/1 shape.
Fields the pilot never extracted are marked unclear/empty and listed in confidence.uncertainFields,
so nobody mistakes them for observations. Re-study these clips (Task 10 gold pass) to fill them."""
import json
import re
import sys

from corpus import REFS_DIR
from corpus.schema import IMPERFECTIONS, validate

CLAY_REVEAL = {"ref01", "ref02", "ref03", "ref04", "ref06", "ref09", "ref10", "ref12"}  # PILOT-NOTES §3
_FRAMES = re.compile(r"Frames? ([0-9][0-9 ,\-and]*)")
NOTE = "pilot-migrated: overlays, surfaceState, secondarySubjects, cameraImperfections not extracted"


def _layout(aspect):
    a = aspect.lower()
    if aspect in ("9:16", "16:9", "1:1", "4:5"):
        return aspect, {"kind": "full", "contentAspect": aspect}
    kind = "rotated" if "rotated" in a else "split" if ("stacked" in a or "two" in a) else "other"
    content = "16:9" if "16:9" in a else "other"
    return "9:16", {"kind": kind, "contentAspect": content}


def _render_pass(ref_id, notes):
    n = notes.lower()
    for word, rp in (("split", "split"), ("viewport", "viewport"), ("clay", "clay")):
        if word in n:
            return rp
    return "unclear" if ref_id in CLAY_REVEAL else "final"


def _retile(rec):
    """The pilot merged some shots (ref02, ref03, ref11): shotCount and cutTimesS disagree with the
    shot list, and ref11 has a gap. Rebuild the shot list on the union of cut times: a shot that spans
    a cut is split (both halves keep its fields), a gap becomes an all-unclear shot."""
    dur = rec["format"]["durationS"]
    cuts = sorted(set([round(c, 3) for c in rec["format"].get("cutTimesS", [])]
                      + [round(s["startS"], 3) for s in rec["shots"][1:]]))
    bounds = [0.0] + [c for c in cuts if 0 < c < dur] + [dur]
    out = []
    for a, b in zip(bounds, bounds[1:]):
        src = next((s for s in rec["shots"] if s["startS"] - 0.05 <= a and b <= s["endS"] + 0.05), None)
        sh = dict(src) if src else {"cameraMove": "unclear", "lensClass": "unclear", "cameraHeight": "unclear",
                                    "dutchTilt": False, "focus": "unclear", "subjectMotion": "unclear",
                                    "notes": "pilot gap: not studied"}
        if src is None or (src["startS"], src["endS"]) != (a, b):
            rec.setdefault("confidence", {"overall": "mid", "uncertainFields": []})
            rec["confidence"].setdefault("uncertainFields", []).append(f"shots {a:g}-{b:g} s re-tiled from the pilot")
        sh.update(startS=a, endS=b)
        out.append(sh)
    return out


def migrate(rec):
    if "method" in rec:
        return rec
    rec = dict(rec)
    aspect, layout = _layout(rec["format"]["aspect"])
    rec["format"] = {**rec["format"], "aspect": aspect}
    rec["layout"] = layout
    rec["source"] = {"kind": "owner", "platform": "owner-refs", "url": None, "downloaded": True,
                     "selection": "hand", "studiedAt": "2026-09-24", "note": rec.get("source")}
    rec["method"] = "local_frames"
    rec["qualityEstimate"] = "T3"   # owner-supplied "what a masterpiece looks like" (assets-in/refs/MANIFEST.md)
    rec["shots"] = _retile(rec)
    rec["format"]["shotCount"] = len(rec["shots"])
    rec["format"]["cutTimesS"] = [sh["startS"] for sh in rec["shots"][1:]]
    ev = {"format.cutTimesS": ["pilot: ffmpeg scene 0.3 + 0.12, 6 frames per clip"]} if len(rec["shots"]) > 1 else {}
    for i, sh in enumerate(rec["shots"]):
        if sh["cameraMove"] == "other":
            sh["cameraMove"] = "unclear"  # the pilot used "other" for "could not tell" (33 of 48 shots)
        sh["renderPass"] = _render_pass(rec["id"], sh.get("notes", ""))
        m = _FRAMES.search(sh.get("notes", ""))
        frames = re.findall(r"\d+", m.group(1)) if m else []
        if sh["cameraMove"] != "unclear" and len(frames) < 2:
            sh["cameraMove"] = "unclear"  # a move needs two frames of evidence (PILOT-NOTES §1)
        if sh["cameraMove"] != "unclear":
            ev[f"shots[{i}].cameraMove"] = [f"pilot frames {m.group(1).strip()}"]
    rec["evidence"] = ev
    rec["overlays"], rec["surfaceState"], rec["secondarySubjects"] = [], [], []
    rec["transitions"] = [{"atS": t, "kind": "cut"} for t in rec["format"].get("cutTimesS", [])]
    rec["cameraImperfections"] = {k: "unclear" for k in IMPERFECTIONS}
    conf = dict(rec.get("confidence", {"overall": "mid", "uncertainFields": []}))
    conf["uncertainFields"] = list(conf.get("uncertainFields", [])) + [NOTE]
    rec["confidence"] = conf
    return rec


def main():
    bad = 0
    for path in sorted(REFS_DIR.glob("*.json")):
        rec = migrate(json.loads(path.read_text(encoding="utf-8")))
        probs = validate(rec)
        path.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        for p in probs:
            bad += 1
            print(f"{path.stem}: {p}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
