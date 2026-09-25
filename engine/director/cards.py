"""The subject card: what the director sees about the upload. Measured facts only, rounded. File
names and clip names are NOT here: they are untrusted text and travel in a fenced block (request.py)."""
from engine.director.family import family


def profile_card(p):
    return {
        "family": family(p), "sizeM": [round(x, 3) for x in p.sizeM], "longestM": round(p.longest, 3),
        "sizeClass": p.sizeClass, "categoryHint": p.categoryHint,
        "materials": [{"class": m["class"], "share": round(m["share"], 2)} for m in p.materials[:5]],
        "glossShare": round(p.glossShare, 2), "rigged": p.rigged, "animated": p.animated,
        "detailPoints": [{"index": i, "kind": d["kind"], "score": round(d.get("score", 0.0), 2)}
                         for i, d in enumerate(p.detailPoints[:8])],
        "parts": len(p.parts), "wheels": len(p.wheels),
        "animationClips": [{"index": c["index"], "durationS": round(c["durationS"], 2)}
                           for c in getattr(p, "animationClips", [])],
    }
