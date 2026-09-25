"""Measured ([M]/[V]) failures reroll the offending shot (TIERS §3). One model call that may change
only that shot's camera/target/purpose, then a deterministic seeded re-angle, else unchanged."""
import copy
import random

from engine.catalog import Catalog
from engine.checker import check
from engine.compiler.timeline import shot_index
from engine.director.fallback import slot_camera
from engine.director.llm import LLMError
from engine.director.output_schema import decompact, default_compact, scene_output_schema
from engine.director.pipeline import MAX_TOKENS
from engine.director.request import reroll_message
from engine.director.rulebook import load_rulebook
from engine.director.sanitize import menu_issues, parse_output

SHOT_KEYS = ("camera", "target", "purpose")


def shots_for_failures(script, failures):
    """{item_id: [1-based frames]} -> {shot index: [item ids]} (frame f shows t = (f - 1) / fps)."""
    fps, out = script["format"]["fps"], {}
    for iid, frames in failures.items():
        for f in frames:
            ids = out.setdefault(shot_index(script["shots"], (f - 1) / fps), [])
            if iid not in ids:
                ids.append(iid)
    return dict(sorted(out.items()))


def _splice(script, index, new_shot):
    """Only the shot's camera / target / purpose change; its times and every other field stay."""
    s = copy.deepcopy(script)
    sh = s["shots"][index]
    if isinstance(new_shot.get("camera"), dict) and new_shot["camera"].get("id") != sh["camera"]["id"]:
        sh.pop("target", None)  # the new camera may not use the old target; check() re-defaults a detail target
    for k in SHOT_KEYS:
        if k in new_shot:
            sh[k] = copy.deepcopy(new_shot[k])
    return s


def _ask_model(script, index, reasons, provider, job, catalog, system):
    messages = [{"role": "user", "content": reroll_message(index, script, reasons, job.fmt)}]
    # compact by default; with VALORA_DIRECTOR_SCHEMA=full, compact only if the API rejects the full one
    for compact in ((True,) if default_compact() else (False, True)):
        try:
            res = provider.generate(system=system, schema=scene_output_schema(catalog, compact=compact),
                                    max_tokens=MAX_TOKENS, messages=messages)
        except LLMError as e:
            if e.kind == "schema_too_complex" and not compact:
                continue
            return None
        raw, _ = parse_output(res.text) if res.stop_reason == "end_turn" else (None, [])
        return decompact(raw)
    return None


def reroll_shot(script, index, reasons, *, profile, provider, job, catalog=None, rulebook=None):
    catalog = catalog or Catalog.load()
    system, _ = rulebook or load_rulebook()
    raw = _ask_model(script, index, reasons, provider, job, catalog, system)
    shots = raw.get("shots") if isinstance(raw, dict) else None
    if isinstance(shots, list) and len(shots) == len(script["shots"]) and isinstance(shots[index], dict):
        try:
            spliced = _splice(script, index, shots[index])
            r = None if menu_issues(spliced, catalog) else check(spliced, profile, catalog)
        except Exception:  # noqa: BLE001 - a junk reply falls through to the deterministic re-angle
            r = None
        if r is not None and r.ok and r.script["shots"][index] != script["shots"][index]:
            return r.script, "llm"
    purpose = script["shots"][index].get("purpose", "motion")
    rng = random.Random(f"reroll:{script['seed']}:{index}")
    for _ in range(4):
        j = round(rng.uniform(-25.0, 25.0), 1)
        cam = slot_camera(purpose, index, job.family, jitter=j, detail_jitter=j)
        r = check(_splice(script, index, {"camera": cam}), profile, catalog)
        if r.ok and r.script["shots"][index] != script["shots"][index]:
            return r.script, "deterministic"
    return copy.deepcopy(script), "unchanged"
