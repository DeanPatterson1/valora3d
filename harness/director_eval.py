"""Director eval (spec §9): prompts x models -> engine.director.pipeline.direct -> report-only scores.
Headline metric: checker pass rate before repair (share of jobs whose FIRST model reply passed the
checker, in-place checker repairs allowed, before any repair call)."""
import json
from pathlib import Path

PROMPTS = Path(__file__).with_name("prompts")


def load_prompt_set(name="v1"):
    data = json.loads((PROMPTS / f"{name}.json").read_text(encoding="utf-8"))
    return data["prompts"], data.get("markerSets", {})


def markers_for(spec, profile):
    """Marker dicts for one marker set, anchored on the profile's measured detail points (the subject
    surface); a missing detail point falls back to the subject centre."""
    out = []
    for m in spec:
        kind, _, idx = m["from"].partition(":")
        d = profile.detailPoints[int(idx)] if kind == "detail" and int(idx) < len(profile.detailPoints) else None
        anchor = {"space": "placed", "point": list(d["point"]) if d else list(profile.center)}
        if d and d.get("normal"):
            anchor["normal"] = list(d["normal"])
        mk = {"id": m["id"], "text": m["text"], "anchor": anchor}
        if "timeS" in m:
            mk["timeS"] = m["timeS"]
        out.append(mk)
    return out


def expected_unsupported(case, profile, catalog=None):
    """The capability tags this case must report for this model, or None when it expects nothing.
    A {"default", "animated"} expectation picks "animated" when the model's clip is playable."""
    exp = case.get("expectUnsupported")
    if exp is None:
        return None
    if isinstance(exp, dict):
        from engine.catalog import Catalog
        cat = catalog or Catalog.load()
        playable = "motion.character_clip" in cat.capabilities(profile)
        return list(exp["animated"] if playable else exp["default"])
    return list(exp)
