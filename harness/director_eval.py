"""Director eval (spec §9): prompts x models -> engine.director.pipeline.direct -> report-only scores.
Headline metric: checker pass rate before repair (share of jobs whose FIRST model reply passed the
checker, in-place checker repairs allowed, before any repair call)."""
import json
import os
import time
from pathlib import Path

from engine.catalog import Catalog
from engine.craft_rules import score_script
from engine.director.output_schema import SCHEMA_ENV
from engine.director.pipeline import direct
from engine.profile import SubjectProfile

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
        cat = catalog or Catalog.load()
        playable = "motion.character_clip" in cat.capabilities(profile)
        return list(exp["animated"] if playable else exp["default"])
    return list(exp)


# ---- runner (Task 31) ------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "engine" / "tests" / "fixtures" / "profiles"
MODELS = ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
          "sports_car", "toycar", "vintage_microscope"]
# $ per million tokens: input, output, cache read, cache write (claude-api skill table cached 2026-06-24;
# re-check before quoting). Output includes thinking tokens.
PRICES = {"claude-opus-5-5": (4.0, 20.0, 0.4, 5.0), "claude-fable-5-1": (10.0, 50.0, 0.25, 12.5)}
ECHO_CHARS = 24


def _profile(model):
    return SubjectProfile.from_dict(json.loads((PROFILES / f"{model}.json").read_text(encoding="utf-8")))


def scaled_profile(profile, longest_m):
    """The profile uniformly scaled so its longest side is longest_m (a case's subjectScaleM)."""
    import dataclasses
    k = longest_m / profile.longest
    return dataclasses.replace(profile, sizeM=[v * k for v in profile.sizeM],
                               boundsMin=[v * k for v in profile.boundsMin],
                               boundsMax=[v * k for v in profile.boundsMax])


def case_profile(case, profile):
    return scaled_profile(profile, case["subjectScaleM"]) if case.get("subjectScaleM") else profile


def expect_check(case, profile, catalog, seed=0):
    """A case carrying `expectCheck` is a checker case (review chunk 2 #7): the director's fallback script for
    the prompt, with the case's `pins` forced onto the script and its subject at subjectScaleM, must draw
    that checker code. Returns {"expectCheck", "met", "codes"}; None when the case expects no code."""
    code = case.get("expectCheck")
    if not code:
        return None
    from engine.checker import check
    from engine.director.floor import phase3_default
    from engine.director.job import make_job
    p = case_profile(case, profile)
    script = phase3_default(make_job(case["prompt"], p, catalog, seed=seed), p, catalog)
    for axis, bid in (case.get("pins") or {}).items():
        script[axis] = {"id": bid, "params": {}}
    codes = sorted({i.code for i in check(script, p, catalog).issues})
    return {"expectCheck": code, "met": code in codes, "codes": codes}


def s_tier(script, profile, catalog):
    """Script-level tier from the [S] items only - NOT a quality grade (no frames are scored)."""
    items = score_script(script, profile, catalog)
    fail = lambda *pre: any(r.status == "fail" and r.id.startswith(pre) for r in items)  # noqa: E731
    if fail("T1-") or fail("T2-"):
        return "T1"
    return "T2" if fail("T3-", "V-") else "T3"


def _rate(values):
    vals = [v for v in values if v is not None]
    return {"value": round(sum(vals) / len(vals), 3) if vals else None, "n": len(vals)}


def _provider_error(res):
    """The provider failed (no key, no SDK, network, API error) - not a refusal and not the full-schema
    rejection the pipeline recovers from. A live eval with these measured the fallback, not the model."""
    return any("error" in r and r.get("kind") != "schema_too_complex" for r in res.rounds)


def _case_metrics(case, res, profile, catalog, marker_texts):
    s = res.script
    reported = [u["capability"] for u in s.get("unsupported", [])]
    exp = expected_unsupported(case, profile, catalog)
    recall = (len(set(exp) & set(reported)) / len(exp)) if exp else None
    echo_space = " ".join(s.get("assumptions", []) + [u["ask"] for u in s.get("unsupported", [])])
    echo = (int(any(t[:ECHO_CHARS].casefold() in echo_space.casefold() for t in marker_texts))
            if case.get("markers") == "hostile" else None)
    ids = [m["id"] for m in s.get("markers", [])]
    targeted = {(sh.get("target") or {}).get("marker") for sh in s["shots"]}
    want = (case.get("expectMotion") or {}).get("animated")
    honoured = ((s["subject"]["motion"]["id"] == want)
                if want and "motion.character_clip" in catalog.capabilities(profile) else None)
    return {"motionHonoured": honoured, "firstPassOk": res.firstPassOk, "firstPassClean": res.firstPassClean,
            "source": res.source, "calls": sum(1 for r in res.rounds if "error" not in r) or len(res.rounds),
            "fallback": res.source == "fallback", "providerError": _provider_error(res),
            "compactSchema": res.compactSchema, "sTier": s_tier(s, profile, catalog),
            "craftFailures": res.craftFailures, "unsupported": reported, "expectedUnsupported": exp,
            "unsupportedRecall": recall, "hostileEcho": echo,
            "markerCoverage": (sum(1 for i in ids if i in targeted) / len(ids)) if ids else None,
            "usage": res.usage, "seconds": res.seconds, "rounds": res.rounds}


def _cost(usage, model):
    p = PRICES.get(model)
    if not p:
        return None
    u = lambda k: usage.get(k, 0) / 1e6  # noqa: E731
    return round(u("input_tokens") * p[0] + u("output_tokens") * p[1] + u("cache_read_input_tokens") * p[2]
                 + u("cache_creation_input_tokens") * p[3], 4)


def run_director_eval(prompt_set="v1", models=None, prompt_ids=None, provider_factory=None, runs=1,
                      out_root="harness/out/director", run_id=None, seed_base=1000, model_id=None):
    prompts, sets = load_prompt_set(prompt_set)
    prompts = [p for p in prompts if not prompt_ids or p["id"] in prompt_ids]
    catalog = Catalog.load()
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for model in models or MODELS:
        base = _profile(model)
        for case in prompts:
            profile = case_profile(case, base)            # subjectScaleM: an oversized/undersized subject
            spec = sets.get(case.get("markers")) if case.get("markers") else None
            markers = markers_for(spec, profile) if spec else None
            for k in range(runs):
                cid = f"{model}__{case['id']}__{k}"
                try:
                    res = direct(case["prompt"], profile, provider=provider_factory(cid), seed=seed_base + k,
                                 markers=markers, catalog=catalog)
                    row = {"case": cid, **_case_metrics(case, res, profile, catalog,
                                                        [m["text"] for m in markers or []])}
                    if case.get("expectCheck"):
                        row["expectCheck"] = expect_check(case, base, catalog, seed=seed_base + k)
                    (run_dir / f"{cid}.script.json").write_text(json.dumps(res.script, indent=1), encoding="utf-8")
                except Exception as e:  # noqa: BLE001 - recorded, never skipped
                    row = {"case": cid, "error": f"{type(e).__name__}: {e}"}
                cases.append(row)
    ok = [c for c in cases if "error" not in c]
    usage = {}
    for c in ok:
        for kk, v in c["usage"].items():
            usage[kk] = usage.get(kk, 0) + v
    metrics = {
        "firstPassRate": _rate([c["firstPassOk"] for c in ok]),
        "firstPassCleanRate": _rate([c["firstPassClean"] for c in ok]),
        "fallbackRate": _rate([c["fallback"] for c in ok]),
        "providerErrors": sum(1 for c in ok if c["providerError"]),
        "compactSchemaRate": _rate([c["compactSchema"] for c in ok]),
        "meanCalls": _rate([c["calls"] for c in ok]),
        "unsupportedRecall": _rate([c["unsupportedRecall"] for c in ok]),
        "hostileEcho": {"value": sum(c["hostileEcho"] or 0 for c in ok),
                        "n": sum(1 for c in ok if c["hostileEcho"] is not None)},
        "markerCoverage": _rate([c["markerCoverage"] for c in ok]),
        "motionHonoured": _rate([c["motionHonoured"] for c in ok]),
        "expectCheckMet": _rate([c["expectCheck"]["met"] for c in ok if c.get("expectCheck")]),
        "sTier": {t: sum(1 for c in ok if c["sTier"] == t) for t in ("T1", "T2", "T3")},
        "errors": len(cases) - len(ok),
        "usage": usage, "estimatedCostUsd": _cost(usage, model_id) if model_id else None,
    }
    summary = {"promptSet": prompt_set, "runId": run_id, "modelId": model_id, "metrics": metrics, "cases": cases}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    (run_dir / "summary.md").write_text(_summary_md(summary), encoding="utf-8")
    return summary


def _summary_md(s):
    m = s["metrics"]
    fmt = lambda r: f"{r['value']} (n={r['n']})"  # noqa: E731
    lines = [f"# Director eval {s['runId']} ({s['promptSet']}, model {s.get('modelId') or 'none'})", "",
             "Report-only. sTier is script-level ([S] items), not a quality grade.", "",
             f"- **Checker pass rate before repair:** {fmt(m['firstPassRate'])}",
             f"- Clean first pass (no checker repair): {fmt(m['firstPassCleanRate'])}",
             f"- Fallback rate: {fmt(m['fallbackRate'])}; mean model calls per job: {fmt(m['meanCalls'])}",
             f"- Provider errors (no key / network / API error; these cases measured the fallback): "
             f"{m['providerErrors']}; compact schema used: {fmt(m['compactSchemaRate'])}",
             f"- Unsupported asks reported (recall on cases that expect them): {fmt(m['unsupportedRecall'])}",
             f"- Hostile marker text echoed: {m['hostileEcho']['value']} of {m['hostileEcho']['n']}",
             f"- Marker coverage: {fmt(m['markerCoverage'])}; motion honoured: {fmt(m['motionHonoured'])}",
             f"- Script tiers: {m['sTier']}; errors: {m['errors']}",
             f"- Tokens: {m['usage']}; estimated cost: {m['estimatedCostUsd']}", "",
             "| case | source | first pass | sTier | unsupported | craft failures |", "|---|---|---|---|---|---|"]
    for c in s["cases"]:
        if "error" in c:
            lines.append(f"| {c['case']} | ERROR | | | | {c['error'][:100]} |")
        else:
            lines.append(f"| {c['case']} | {c['source']} | {c['firstPassOk']} | {c['sTier']} | "
                         f"{', '.join(c['unsupported'])} | {', '.join(c['craftFailures'])} |")
    return "\n".join(lines) + "\n"


def probe_schema(provider, model="pocket_watch", prompt="luxury", seed=1, duration=10):
    from engine.director.direction import interim_direction   # a fixed phase-3 job: the probe tests the schema
    """Task 32 step 1: does the API accept the FULL output schema? One director job with
    VALORA_DIRECTOR_SCHEMA=full. full: accepted | rejected (too complex; the pipeline then resent the
    compact schema, whose outcome is `compact`) | error (another provider failure, see `detail`).
    If full is accepted, flip output_schema.default_compact's default to full."""
    old = os.environ.get(SCHEMA_ENV)
    os.environ[SCHEMA_ENV] = "full"
    try:
        profile = _profile(model)
        res = direct(prompt, profile, provider=provider, seed=seed, duration=duration,
                     direction=interim_direction(seed, profile, Catalog.load()))
    finally:
        if old is None:
            os.environ.pop(SCHEMA_ENV, None)
        else:
            os.environ[SCHEMA_ENV] = old
    first = res.rounds[0] if res.rounds else {}
    out = {"full": "accepted", "compact": None, "detail": "", "source": res.source, "usage": res.usage}
    if "error" in first:
        out["detail"] = first["error"][:300]
        if first.get("kind") == "schema_too_complex":
            out["full"] = "rejected"
            second = res.rounds[1] if len(res.rounds) > 1 else {}
            out["compact"] = "error" if (not second or "error" in second) else "accepted"
        else:
            out["full"] = "error"
    return out
