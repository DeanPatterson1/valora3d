"""Spec §6 layer 1: details always differ. Seeded, small, in-range offsets to a whitelist of look params
(dice.json detailParams) that the script left unset. Values the script set are kept. Deterministic by
seed and pipeline-owned: applied to LLM and fallback scripts alike before the checker, so builders get
seed-driven variation through their params and the script still fully describes the render."""
import random

from engine.director.axes import DICE


def _vary(ref, kind, path, seed, catalog, table):
    if not isinstance(ref, dict) or not isinstance(ref.get("id"), str):
        return
    fracs, m = table.get(f"{kind}/{ref['id']}"), catalog.get(kind, ref["id"])
    if not fracs or m is None:
        return
    params = ref.setdefault("params", {})
    if not isinstance(params, dict):
        return
    rng = random.Random(f"detail:{seed}:{path}")
    for name, frac in sorted(fracs.items()):
        spec = m["params"].get(name)
        if name in params or not spec or spec["type"] != "number":
            continue
        v = spec["default"] + rng.uniform(-frac, frac) * (spec["max"] - spec["min"])
        params[name] = round(min(spec["max"], max(spec["min"], v)), 4)


def vary_details(script, seed, catalog, dice=None):
    table = (dice or DICE)["detailParams"]
    _vary(script.get("world"), "world", "world", seed, catalog, table)
    _vary(script.get("lighting"), "lighting", "lighting", seed, catalog, table)
    for i, e in enumerate(script.get("effects") if isinstance(script.get("effects"), list) else []):
        _vary(e, "effect", f"effects[{i}]", seed, catalog, table)
    return script
