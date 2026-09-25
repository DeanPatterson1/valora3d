"""Spec §9a use 1: cluster corpus records into block candidates and rank them by frequency x fit.
Advisory until >= TRUST_N records (the ranking then reorders a plan chunk's optional tasks).

Record fields (corpus/schema.py, valora.ref/1): world.type and shots[].cameraMove / subjectMotion are
enums; world.weather, world.atmosphere, effects and simulation are free text. Free text is reduced to
keywords (WEATHER_WORDS, EFFECT_WORDS) so "fog, snowfall" counts as weather:fog + weather:snow; an effect
string that matches no keyword is kept whole as a never-thought-of candidate."""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "corpus" / "backlog.json"
TRUST_N = 30  # (eng) same bar as the dice weight floor in the phase-4 register
FIELDS = {"world": ("world", "type")}          # enum fields; weather is free text (world.weather + atmosphere)
SKIP = {"", "none", "dry", "clear", "n/a", "unclear", "other"}   # no information about a block
WEATHER_WORDS = (("rain", "rain"), ("drizzle", "rain"), ("downpour", "rain"), ("snow", "snow"), ("fog", "fog"),
                 ("mist", "fog"), ("wet", "wet"), ("puddle", "wet"), ("haze", "haze"))
EFFECT_WORDS = (("steam", "steam"), ("smoke", "smoke"), ("exhaust", "exhaust"), ("leaf", "leaves"),
                ("leaves", "leaves"), ("dust", "dust"), ("confetti", "confetti"), ("spark", "sparks"),
                ("bubble", "bubbles"))
BLOCK_MAP = {  # corpus value -> catalog ref (None = no block yet)
    "world:cyclorama": "world/studio_cyc", "world:studio": "world/studio_cyc",
    "world:street": "world/night_street", "world:city": "world/night_street", "world:courtyard": "world/rain_courtyard",
    "world:nature": "world/golden_field", "world:field": "world/golden_field",
    "world:interior": None, "world:abstract": None, "world:water": None, "world:highway": None,
    "world:space": None, "world:tunnel": None,
    "camera:push": "camera/low_hero_push", "camera:orbit": "camera/arc_orbit", "camera:arc": "camera/arc_orbit",
    "camera:slide": "camera/profile_slide", "camera:rise": "camera/reveal_rise",
    "camera:handheld": "camera/handheld_operator", "camera:tracking": "camera/rolling_track",
    "camera:chase": "camera/rolling_track", "camera:macro": "camera/macro_detail", "camera:fpv": None,
    "camera:locked": None, "camera:dutch": "camera/dutch_hero", "camera:pull": None, "camera:fall": None,
    "camera:tilt": None, "camera:pan": None,
    "motion:static": "motion/static",
    "motion:drive": "motion/drive", "motion:driving": "motion/drive", "motion:roll": "motion/roll",
    "motion:drop": "motion/drop_settle", "motion:falling": "motion/drop_settle",
    "motion:float": "motion/float_drift", "motion:floating": "motion/float_drift", "motion:spin": "motion/plinth_spin",
    "motion:toss": "motion/toss_tumble", "motion:topple": "motion/topple", "motion:slide": "motion/slide_in",
    "motion:sim": None, "motion:assembly": None,
    "weather:rain": "effect/rain", "weather:snow": "effect/snow", "weather:fog": "effect/ground_fog",
    "weather:wet": "effect/wet_surface", "weather:haze": "effect/haze_volume",
    "effect:steam": None, "effect:smoke": None, "effect:leaves": None, "effect:dust": None,
    "effect:exhaust": None, "effect:confetti": None, "effect:sparks": None, "effect:bubbles": None,
}
FIT = {"world": 1.0, "camera": 1.0, "motion": 0.9, "weather": 0.9, "effect": 0.7}   # (eng) Valora3D fit by area


def _get(d, path):
    for k in path:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def _words(text, table):
    t = text.lower()
    return {name for word, name in table if re.search(rf"\b{word}", t)}


def _texts(v):
    return [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def _keys(rec):
    out = set()
    for area, path in FIELDS.items():
        v = _get(rec, path)
        if isinstance(v, str) and v.strip().lower() not in SKIP:
            out.add(f"{area}:{v.strip().lower()}")
    for t in _texts(_get(rec, ("world", "weather"))) + _texts(_get(rec, ("world", "atmosphere"))) \
            + _texts(rec.get("effects")) + _texts(rec.get("simulation")):
        out |= {f"weather:{w}" for w in _words(t, WEATHER_WORDS)}
    for sh in rec.get("shots", []) if isinstance(rec.get("shots"), list) else []:
        for area, k in (("camera", "cameraMove"), ("motion", "subjectMotion")):
            v = sh.get(k) if isinstance(sh, dict) else None
            if isinstance(v, str) and v.strip().lower() not in SKIP:
                out.add(f"{area}:{v.strip().lower()}")
    for t in _texts(rec.get("simulation")):
        out |= {f"effect:{e}" for e in _words(t, EFFECT_WORDS)}
    for t in _texts(rec.get("effects")):
        hits = _words(t, EFFECT_WORDS)
        if hits:
            out |= {f"effect:{e}" for e in hits}
        elif not _words(t, WEATHER_WORDS):
            slug = re.sub(r"\s*\(.*?\)", "", t).strip().lower()
            if slug not in SKIP:
                out.add(f"effect:{slug}")
    return out


def rank(records, catalog_ids):
    counts = Counter(k for r in records for k in _keys(r))
    cands = []
    for key, n in counts.items():
        area = key.split(":")[0]
        block = BLOCK_MAP.get(key)
        fit = FIT.get(area, 0.5)
        cands.append({"key": key, "count": n, "share": round(n / len(records), 3), "fit": fit,
                      "score": round(n / len(records) * fit, 4), "block": block,
                      "exists": bool(block and block in catalog_ids), "novel": key not in BLOCK_MAP})
    cands.sort(key=lambda c: (-c["score"], c["key"]))
    return {"schema": "valora.backlog/1", "n": len(records), "trusted": len(records) >= TRUST_N, "candidates": cands}


def main(argv=None):
    from corpus import REFS_DIR
    from corpus.stats import eligible          # the same record filter the stats use
    from engine.catalog import Catalog
    cat = Catalog.load()
    ids = {f"{k}/{b}" for k in ("world", "camera", "motion", "effect") for b in cat.ids(k)}
    recs = eligible([json.loads(p.read_text(encoding="utf-8")) for p in sorted(REFS_DIR.glob("*.json"))])
    doc = rank(recs, ids)
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{doc['n']} records, trusted={doc['trusted']}; top: " + ", ".join(c["key"] for c in doc["candidates"][:8]))
    return 0
