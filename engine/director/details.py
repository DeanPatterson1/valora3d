"""Spec §6 layer 1: details always differ. Seeded, visible but in-taste values for a whitelist of look and
camera params (dice.json detailParams) that the script left unset. Values the script set are kept.
Deterministic by seed and pipeline-owned: applied to LLM and fallback scripts alike before the checker, so
builders get seed-driven variation through their params and the script still fully describes the render.

A rule is one of (all clamped to the catalog range, then to the rule's optional min/max band):
  {"lo": a, "hi": b}   uniform inside a taste window (a taste rule's own numbers, e.g. TG-09 fill 0.25-0.5)
  {"pm": x}            the centre +- x (the author's value, a fallback constant, or the catalog default)
  {"rel": r}           the centre times a factor in [1/(1+r), 1+r] (lenses and distances scale, not add)
  {"byMood": true}     uniform inside dice.json colorTempByMood[<the script's grade preset>]
"family": {<family>: {...}} overrides any of these keys for one subject family (e.g. TG-10 vehicle lenses).
"timed": true marks a param that changes how FAST a move runs (settle, slide): only the fallback, which caps
the rate after varying (T3-14), varies it; an LLM script's unset one keeps its default.
`scale` (0..1] shrinks every offset toward the centre (window rules toward the window's middle); the
fallback retries at a smaller scale when a varied script would score a lower tier than the plain one."""
import math
import random

from engine.director.axes import DICE


def _rng(seed, path, name):
    return random.Random(f"detail:{seed}:{path}:{name}")


def rule_value(rule, centre, spec, rng, *, scale=1.0, family=None, mood=None, dice=None):
    rule = {**rule, **(rule.get("family", {}).get(family, {}) if family else {})}
    lo, hi = max(spec["min"], rule.get("min", spec["min"])), min(spec["max"], rule.get("max", spec["max"]))
    if rule.get("byMood"):
        table = (dice or DICE)["colorTempByMood"]
        rule = {**rule, **dict(zip(("lo", "hi"), table.get(mood, table["default"])))}
    if "lo" in rule:
        a, b = max(lo, rule["lo"]), min(hi, rule["hi"])
        mid = (a + b) / 2.0
        v = mid + (rng.uniform(a, b) - mid) * scale
    elif "rel" in rule:
        v = centre * math.exp(rng.uniform(-1.0, 1.0) * math.log1p(rule["rel"]) * scale)
    else:
        v = centre + rng.uniform(-1.0, 1.0) * rule["pm"] * scale
    return round(min(hi, max(lo, v)), 4)


def vary_params(params, kind, bid, path, seed, catalog, *, centre=None, keep=None, scale=1.0, family=None,
                mood=None, dice=None, timed=False):
    """Seed every numeric param of `kind/bid` that detailParams lists, except the names in `keep` (default:
    the names already in params, i.e. what the author set). `centre` overrides the catalog default."""
    rules, m = (dice or DICE)["detailParams"].get(f"{kind}/{bid}"), catalog.get(kind, bid)
    if not rules or m is None or not isinstance(params, dict):
        return params
    keep = set(params) if keep is None else set(keep)
    for name, rule in sorted(rules.items()):
        spec = m["params"].get(name)
        if name in keep or not spec or spec["type"] != "number" or (rule.get("timed") and not timed):
            continue
        c = (centre or {}).get(name, params.get(name, spec["default"]))
        params[name] = rule_value(rule, c, spec, _rng(seed, path, name), scale=scale, family=family, mood=mood,
                                  dice=dice)
    return params


def _mood(script):
    g = script.get("grade") if isinstance(script.get("grade"), dict) else {}
    p = g.get("params") if isinstance(g.get("params"), dict) else {}
    return p.get("preset")


def _vary(ref, kind, path, seed, catalog, centres, **kw):
    if not isinstance(ref, dict) or not isinstance(ref.get("id"), str):
        return
    params = ref.setdefault("params", {})
    vary_params(params, kind, ref["id"], path, seed, catalog, centre=centres.get(f"{kind}/{ref['id']}"), **kw)


def vary_details(script, seed, catalog, dice=None, centres=None, scale=1.0, family=None):
    """centres: {"kind/id": {param: value}} to vary around instead of the catalog default (the fallback
    centres on its phase-3 constants). Cameras: only the params each shot left unset."""
    centres = centres or {}
    kw = {"scale": scale, "family": family, "mood": _mood(script), "dice": dice}
    _vary(script.get("world"), "world", "world", seed, catalog, centres, **kw)
    _vary(script.get("lighting"), "lighting", "lighting", seed, catalog, centres, **kw)
    for i, e in enumerate(script.get("effects") if isinstance(script.get("effects"), list) else []):
        _vary(e, "effect", f"effects[{i}]", seed, catalog, centres, **kw)
    for i, sh in enumerate(script.get("shots") if isinstance(script.get("shots"), list) else []):
        if isinstance(sh, dict):
            _vary(sh.get("camera"), "camera", f"shots[{i}].camera", seed, catalog, centres, **kw)
    return script


def reverse_travel(seed, path, dice=None):
    """Seeded coin: does this shot travel its arc the other way?"""
    return random.Random(f"detail:{seed}:{path}:travel").random() < (dice or DICE)["detailTiming"]["reverseTravel"]


def vary_lengths(purposes, lengths, duration, seed, catalog, template, *, scale=1.0, dice=None):
    """Shot lengths inside the pace's cadence: the shot COUNT never changes. The hook and the hero take a
    seeded length inside their template slot's lenS window; the middle shots share the rest with seeded
    weights. Any length outside the sequence rules (shotLenS, hookMaxS, lastShotMinS) returns the plan
    unchanged."""
    t, seq = (dice or DICE)["detailTiming"], catalog.get("edit", "sequence")
    rng = random.Random(f"detail:{seed}:shots")
    n = len(lengths)
    if n < 2:
        return list(lengths)
    out = list(lengths)
    if n == 2:
        out[0] = lengths[0] * math.exp(rng.uniform(-1.0, 1.0) * math.log1p(t["twoShotRel"]) * scale)
        out[1] = duration - out[0]
    else:
        win = {s["purpose"]: s["lenS"] for s in template}
        for k, p in ((0, purposes[0]), (n - 1, purposes[-1])):
            if p in win:
                a, b = win[p]
                out[k] = lengths[k] + (rng.uniform(a, b) - lengths[k]) * scale
        w = [1.0 + rng.uniform(-1.0, 1.0) * t["middleWeight"] * scale for _ in range(n - 2)]
        rem = duration - out[0] - out[-1]
        out[1:-1] = [rem * x / sum(w) for x in w]
    lo, hi = seq["shotLenS"]
    ok = (all(lo - 1e-9 <= x <= hi + 1e-9 for x in out) and out[-1] >= seq["lastShotMinS"]
          and (n == 2 or out[0] <= seq["hookMaxS"] + 1e-9) and min(out) >= t["minMiddleS"] - 1e-9)
    return out if ok else list(lengths)


def middle_count(n, duration, rem, pace, seed, catalog, max_per_10s, min_middle_s):
    """A seeded middle-shot count whose total (hook + middle + hero) stays inside the pace's shotsPer10s
    range (the cadence a viewer reads as the pace) and T3-01's cap, with every middle shot inside
    [min_middle_s, shotLenS max]. No allowed count keeps n."""
    seq = catalog.get("edit", "sequence")
    lo, hi = seq["shotsPer10s"][pace]
    lo, hi = math.floor(lo * duration / 10.0), min(math.ceil(hi * duration / 10.0),
                                                   math.floor(max_per_10s * duration / 10.0 + 1e-9))
    allowed = [m for m in range(1, hi) if lo <= m + 2 <= hi and min_middle_s - 1e-9 <= rem / m <= seq["shotLenS"][1]]
    return random.Random(f"detail:{seed}:count").choice(allowed) if allowed else n


LLM_SCALES = (1.0, 0.5)   # (eng) layer-1 scales tried on an LLM script before its plain version


def checked_details(script, seed, catalog, profile, dice=None, scales=LLM_SCALES):
    """Layer 1 on an LLM script, then the checker: the varied script is kept only when it passes at no
    lower tier than the plain one (our jitter must never cost a tier or a repair round); else a smaller
    scale, else the plain script. Returns the CheckResult."""
    import copy

    from engine.checker import check
    from engine.director.floor import script_tier   # lazy: floor -> fallback -> details
    rank = {"T1": 1, "T2": 2, "T3": 3}
    plain = check(copy.deepcopy(script), profile, catalog)
    need = rank[script_tier(plain.script, profile, catalog)] if plain.ok else 0
    for scale in scales:
        r = check(vary_details(copy.deepcopy(script), seed, catalog, dice=dice, scale=scale), profile, catalog)
        if r.ok and rank[script_tier(r.script, profile, catalog)] >= need:
            return r
    return plain
