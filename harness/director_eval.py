"""Director eval (spec §9): prompts x models -> engine.director.pipeline.direct -> report-only scores.
Headline metric: checker pass rate before repair (share of jobs whose FIRST model reply passed the
checker, in-place checker repairs allowed, before any repair call)."""
import json
import os
import time
from pathlib import Path

from engine.catalog import Catalog
from engine.craft_rules import score_script
from engine.director.fallback import FallbackError
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


def expected_delivered(case, profile, catalog=None):
    """The capability tags this case must see delivered by the final script for this model (Task 90), or None.
    Mirrors expected_unsupported: a {"default", "animated"} expectation picks per profile."""
    exp = case.get("expectDelivered")
    if exp is None:
        return None
    if isinstance(exp, dict):
        cat = catalog or Catalog.load()
        playable = "motion.character_clip" in cat.capabilities(profile)
        return list(exp["animated"] if playable else exp["default"])
    return list(exp)


GROWTH = json.loads((Path(__file__).resolve().parents[1] / "engine" / "catalog_growth.json").read_text(encoding="utf-8"))


def ungraded_blocks(script):
    """Growth blocks the script uses whose `golden` is still null (spec §4.3 made visible)."""
    from engine.director.capabilities import _script_refs
    refs = {f"{k}/{b}" for k, b in _script_refs(script)}
    return sorted(r for r in refs if r in GROWTH["blocks"] and GROWTH["blocks"][r].get("golden") is None)


def _direction_axes(script):
    from engine.director.direction import parse_id
    try:
        d = parse_id((script.get("direction") or {}).get("id"))
    except ValueError:
        return {"weather": None, "wind": None}
    return {"weather": d.get("weather"), "wind": d.get("wind")}


# ---- runner (Task 31) ------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "engine" / "tests" / "fixtures" / "profiles"
SYNTHETIC = ROOT / "engine" / "tests" / "fixtures" / "synthetic_profiles"   # TEST ONLY shapes: can, bottle, bare_tube
MODELS = ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
          "sports_car", "toycar", "vintage_microscope"]
# $ per million tokens: input, output, cache read, cache write (claude-api skill table cached 2026-06-24;
# re-check before quoting). Output includes thinking tokens.
PRICES = {"claude-opus-5-5": (4.0, 20.0, 0.4, 5.0), "claude-fable-5-1": (10.0, 50.0, 0.25, 12.5)}
ECHO_CHARS = 24


def _profile(model):
    """An eval model's profile, or a TEST ONLY synthetic shape (fixtures/synthetic_profiles) a case names in its
    `models` (review chunk5 #12)."""
    f = PROFILES / f"{model}.json"
    if not f.exists() and (SYNTHETIC / f"{model}.json").exists():
        f = SYNTHETIC / f"{model}.json"
    return SubjectProfile.from_dict(json.loads(f.read_text(encoding="utf-8")))


class PinUnavailable(ValueError):
    """A case pins a catalog value this (scaled) subject cannot take: the director refuses the job. For a checker
    case that refusal is the expected outcome (review 6 #9); an unknown value stays a plain ValueError."""


# the director's refusals of a subject: the pin it cannot take, or no deliverable script at all (fallback.py)
EXPECTED_REJECTIONS = (PinUnavailable, FallbackError)


def case_models(case, models=None):
    """The models a case runs on (review chunk5 #12): its own `models` when it names them (a drive needs the
    car, a roll the can), filtered by an explicit caller list; otherwise the caller's list or every eval model."""
    own = case.get("models")
    if not own:
        return list(models or MODELS)
    return [m for m in own if models is None or m in models]


def pinned_direction(case, profile, catalog, seed, markers=None):
    """(direction, durationS) with the case's direction `pins` ({axis: value}) held on top of the prompt's own
    pins, or (None, None) when the case pins nothing (review chunk5 #12). The director takes pins from the prompt
    only, so this rolls the job's direction the way variety.choose_direction does (the dice over the viable pool,
    else the interim direction, pins never dropped) and hands it to direct() verbatim with the job's rolled
    duration. A pin this subject cannot take raises: a silent re-roll would measure a different case."""
    pins = case.get("pins") or {}
    if not pins:
        return None, None
    from engine.director.axes import axis_values
    from engine.director.dice import roll
    from engine.director.direction import AXES, direction_of, interim_direction, parse_id
    from engine.director.family import family
    from engine.director.floor import make_viable
    from engine.director.job import base_job
    from engine.director.variety import _load_stats, prompt_pins
    job = base_job(case["prompt"], profile, catalog, seed=seed, markers=markers)
    known = axis_values(profile, catalog, job.fmt, rollable=False)
    bad = sorted(f"{a}={v}" for a, v in pins.items() if a not in AXES or v not in known[a])
    if bad:
        exists = all(a == "world" and v in catalog.selectable_ids("world") for a, v in pins.items()
                     if a not in AXES or v not in known[a])
        raise (PinUnavailable if exists else ValueError)(f"case pins this subject cannot take: {', '.join(bad)}")
    pins = {**prompt_pins(job.prompt, profile, catalog, job.fmt), **pins}
    r = roll(seed, axis_values(profile, catalog, job.fmt), pins=pins, viable=make_viable(job, profile, catalog),
             family_name=family(profile), stats=_load_stats(), catalog=catalog)
    if r.axes is None:
        d = direction_of({**parse_id(interim_direction(seed, profile, catalog).id), **pins}, "interim", pinned=pins)
    else:
        d = direction_of(r.axes, "dice", pinned=pins)
    return d, job.fmt["durationS"]


def scaled_profile(profile, longest_m):
    """The profile uniformly scaled so its longest side is longest_m (a case's subjectScaleM). Every placed
    length scales by k (points, radii, widths, travel, the placement factor), every area by k squared; shares,
    normals, axes, ratios and source-unit facts do not move. Size class and category are re-measured
    (review chunk 4 #4: a half-scaled profile framed and judged an internally inconsistent subject)."""
    import copy
    import dataclasses
    from engine.ingest.measure import category_hint, size_class
    k = longest_m / profile.longest
    v = lambda xs: [x * k for x in xs]  # noqa: E731

    def each(items, pts=(), lens=(), areas=(), polylines=()):
        out = []
        for it in copy.deepcopy(items):
            for f in pts:
                if it.get(f) is not None:
                    it[f] = v(it[f])
            for f in lens:
                if it.get(f) is not None:
                    it[f] = it[f] * k
            for f in areas:
                if it.get(f) is not None:
                    it[f] = it[f] * k * k
            for f in polylines:
                if it.get(f) is not None:
                    it[f] = [v(q) for q in it[f]]
            out.append(it)
        return out

    size = v(profile.sizeM)
    wheels = each(profile.wheels, pts=("center", "contact"), lens=("radius", "width"))
    veh = dict(profile.vehicle)
    for f in ("wheelbaseM", "trackM", "rideHeightM"):
        if veh.get(f) is not None:
            veh[f] = veh[f] * k
    if veh.get("vehicleClass") is not None:          # review 6 #8: the class is size-dependent (toy below 1 m)
        veh["vehicleClass"] = _vehicle_class(veh, size, wheels)
    return dataclasses.replace(
        profile, sizeM=size, boundsMin=v(profile.boundsMin), boundsMax=v(profile.boundsMax),
        scaleFactor=profile.scaleFactor * k, sizeClass=size_class(max(size)), categoryHint=category_hint(size),
        reflectionTargets=each(profile.reflectionTargets, pts=("point",), areas=("area",)),
        shoulderLine=each(profile.shoulderLine, polylines=("points",)),
        detailPoints=each(profile.detailPoints, pts=("point",)),
        wheels=wheels,
        parts=each(profile.parts, pts=("boundsMin", "boundsMax")),
        surfaceSamples=[v(q) for q in profile.surfaceSamples],
        vehicle=veh,
        groundContacts=each(profile.groundContacts, pts=("center",), lens=("radius",)),
        softParts=copy.deepcopy(profile.softParts),
        danglingParts=each(profile.danglingParts, pts=("pivot", "tip"), lens=("radius", "lengthM")),
        animationClips=each(profile.animationClips, pts=("rootTravelM",)))


def _vehicle_class(veh, size, wheels):
    """engine.ingest.measure.vehicle_facts' class rule on already-measured facts: the length along forwardAxis,
    the ride height and the median wheel radius (ingest's own thresholds, imported, never restated)."""
    from engine.ingest.measure import OFFROAD_CLEARANCE, SPORT_RIDE_R, VEHICLE_TOY_M
    fwd = veh.get("forwardAxis") or []
    radii = sorted(w["radius"] for w in wheels if w.get("radius") is not None)
    if not radii or veh.get("rideHeightM") is None or not any(fwd):
        return veh["vehicleClass"]
    length = size[max(range(len(fwd)), key=lambda i: abs(fwd[i]))]
    r, ride = radii[len(radii) // 2], veh["rideHeightM"]
    return ("toy" if length < VEHICLE_TOY_M else "offroad" if ride >= OFFROAD_CLEARANCE * r
            else "sport" if ride <= SPORT_RIDE_R * r else "comfort")


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
    # the fallback is built for the eval model as ingested (a 9 m subject has no studio fallback at all), then
    # the pins go on and the checker judges it against the scaled subject
    script = phase3_default(make_job(case["prompt"], profile, catalog, seed=seed), profile, catalog)
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
    from engine.director.capabilities import delivers
    want = expected_delivered(case, profile, catalog)
    missing = [t for t in want or [] if not delivers(s, t, catalog)]
    delivered = (1.0 - len(missing) / len(want)) if want else None
    echo_space = " ".join(s.get("assumptions", []) + [u["ask"] for u in s.get("unsupported", [])])
    echo = (int(any(t[:ECHO_CHARS].casefold() in echo_space.casefold() for t in marker_texts))
            if case.get("markers") == "hostile" else None)
    ids = [m["id"] for m in s.get("markers", [])]
    targeted = {(sh.get("target") or {}).get("marker") for sh in s["shots"]}
    anim = (case.get("expectMotion") or {}).get("animated")
    honoured = ((s["subject"]["motion"]["id"] == anim)
                if anim and "motion.character_clip" in catalog.capabilities(profile) else None)
    from harness.score import weather_s_items     # PH-07s / PH-08s / W-01 on the directed script (review chunk3 #7)
    weather = {k: v.status for k, v in weather_s_items(s, catalog, case.get("expectDelivered"), profile).items()}
    return {"weather": weather, "motionHonoured": honoured, "firstPassOk": res.firstPassOk, "firstPassClean": res.firstPassClean,
            "source": res.source, "calls": sum(1 for r in res.rounds if "error" not in r) or len(res.rounds),
            "fallback": res.source == "fallback", "providerError": _provider_error(res),
            "compactSchema": res.compactSchema, "sTier": s_tier(s, profile, catalog),
            "craftFailures": res.craftFailures, "unsupported": reported, "expectedUnsupported": exp,
            "unsupportedRecall": recall, "hostileEcho": echo,
            "expectedDelivered": want, "deliveredRecall": delivered, "deliveredMissing": missing,
            "ungradedBlocks": ungraded_blocks(s), "direction": _direction_axes(s),
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
                      out_root="harness/out/director", run_id=None, seed_base=1000, model_id=None, catalog=None):
    prompts, sets = load_prompt_set(prompt_set)
    prompts = [p for p in prompts if not prompt_ids or p["id"] in prompt_ids]
    catalog = catalog or Catalog.load()
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    order = list(models or MODELS)
    order += [m for c in prompts for m in case_models(c, models) if m not in order]   # synthetic subjects last
    for model in dict.fromkeys(order):
        base = _profile(model)
        for case in prompts:
            if model not in case_models(case, models):
                continue
            profile = case_profile(case, base)            # subjectScaleM: an oversized/undersized subject
            spec = sets.get(case.get("markers")) if case.get("markers") else None
            markers = markers_for(spec, profile) if spec else None
            for k in range(runs):
                cid = f"{model}__{case['id']}__{k}"
                # a checker case is scored on its own (review chunk 4 #3): its subject may be one no world takes,
                # so the director run below can fail by design without losing the expected rejection
                checked = None
                if case.get("expectCheck"):
                    try:
                        checked = expect_check(case, base, catalog, seed=seed_base + k)
                    except Exception as e:  # noqa: BLE001 - recorded, never skipped
                        checked = {"expectCheck": case["expectCheck"], "met": False, "codes": [],
                                   "error": f"{type(e).__name__}: {e}"}
                try:
                    direction, duration = pinned_direction(case, profile, catalog, seed_base + k, markers)
                    res = direct(case["prompt"], profile, provider=provider_factory(cid), seed=seed_base + k,
                                 markers=markers, catalog=catalog, direction=direction, duration=duration)
                    row = {"case": cid, **_case_metrics(case, res, profile, catalog,
                                                        [m["text"] for m in markers or []])}
                    (run_dir / f"{cid}.script.json").write_text(json.dumps(res.script, indent=1), encoding="utf-8")
                except Exception as e:  # noqa: BLE001 - recorded, never skipped
                    err = f"{type(e).__name__}: {e}"
                    # a checker case's director refusal is its expected outcome, not an error (review 6 #9); any
                    # other failure (a bug, an output write) is a genuine error even on a checker case
                    row = ({"case": cid, "checkerOnly": True, "directorError": err}
                           if checked and isinstance(e, EXPECTED_REJECTIONS) else {"case": cid, "error": err})
                if checked:
                    row["expectCheck"] = checked
                cases.append(row)
    ok = [c for c in cases if "error" not in c and not c.get("checkerOnly")]
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
        "deliveredRecall": _rate([c["deliveredRecall"] for c in ok]),
        "ungradedRuns": sum(1 for c in ok if c["ungradedBlocks"]),
        "hostileEcho": {"value": sum(c["hostileEcho"] or 0 for c in ok),
                        "n": sum(1 for c in ok if c["hostileEcho"] is not None)},
        "markerCoverage": _rate([c["markerCoverage"] for c in ok]),
        "motionHonoured": _rate([c["motionHonoured"] for c in ok]),
        "deliveredMet": _rate([c["weather"]["PH-07s"] == "pass" for c in ok if c["weather"]["PH-07s"] != "na"]),
        "expectCheckMet": _rate([c["expectCheck"]["met"] for c in cases if c.get("expectCheck")]),
        "checkerOnly": sum(1 for c in cases if c.get("checkerOnly")),
        "sTier": {t: sum(1 for c in ok if c["sTier"] == t) for t in ("T1", "T2", "T3")},
        "errors": sum(1 for c in cases if "error" in c),
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
             f"- Delivered asks provided by the final script (recall on cases that expect them): "
             f"{fmt(m['deliveredRecall'])}; runs using an ungraded growth block: {m['ungradedRuns']}",
             f"- Hostile marker text echoed: {m['hostileEcho']['value']} of {m['hostileEcho']['n']}",
             f"- Marker coverage: {fmt(m['markerCoverage'])}; motion honoured: {fmt(m['motionHonoured'])}",
             f"- Script tiers: {m['sTier']}; errors: {m['errors']}",
             f"- Tokens: {m['usage']}; estimated cost: {m['estimatedCostUsd']}", "",
             "| case | source | first pass | sTier | unsupported | delivered missing | weather/wind | ungraded | craft failures |",
             "|---|---|---|---|---|---|---|---|---|"]
    for c in s["cases"]:
        if "error" in c:
            lines.append(f"| {c['case']} | ERROR | | | | | | | {c['error'][:100]} |")
        elif c.get("checkerOnly"):
            lines.append(f"| {c['case']} | checker only (expectCheck met: {c['expectCheck']['met']}) | | | | "
                         f"| | | {c['directorError'][:100]} |")
        else:
            lines.append(f"| {c['case']} | {c['source']} | {c['firstPassOk']} | {c['sTier']} | "
                         f"{', '.join(c['unsupported'])} | {', '.join(c['deliveredMissing'])} | "
                         f"{c['direction']['weather']}/{c['direction']['wind']} | {', '.join(c['ungradedBlocks'])} | "
                         f"{', '.join(c['craftFailures'])} |")
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
