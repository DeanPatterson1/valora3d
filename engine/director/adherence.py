"""Keep the LLM on the rolled direction (spec §3: variety comes from the dice; §11: the LLM converges on
one safe look). Values resolve catalog defaults. Enforced on vague prompts and for pinned axes:
- mood swaps any grade for mood_grade(preset); tone and pace are set in place;
- the pace is then checked as CUT (measured shot count, floor.cadence_ok);
- a cadence, world or opener mismatch is an error, which goes back to the LLM through the repair loop.
Otherwise every mismatch is info-level drift (measured, not changed).
The phase-3 interim direction (source 'interim': a given phase-3 job, or no viable dice roll) keeps its
phase-3 behaviour: only its pins are enforced (should_enforce), so the frozen baseline still reproduces."""
from engine.director.axes import opener_of
from engine.director.fallback import MIN_SEQ_S
from engine.director.floor import cadence_ok, cadence_range
from engine.issues import Issue

_PATHS = {"mood": ("grade", "preset", "mood_grade"), "pace": ("edit", "pace", "sequence"),
          "tone": ("world", "tone", "studio_cyc")}


def _value(script, axis, catalog):
    """The value as it will render. An ABSENT grade/edit counts as the catalog default block with its
    default params (mood_grade's default preset, sequence's default pace)."""
    key, param, bid = _PATHS[axis]
    ref = script.get(key)
    if ref is None:
        return catalog.get(key, bid)["params"][param]["default"]
    if not isinstance(ref, dict):
        return None
    if ref.get("id") != bid:
        return "clean" if axis == "mood" and ref.get("id") == "neutral_film" else f"<{ref.get('id')}>"
    params = ref.get("params") if isinstance(ref.get("params"), dict) else {}
    return params.get(param, catalog.get(key, bid)["params"][param]["default"])


def drift(script, d, catalog):
    out = [a for a in _PATHS if _value(script, a, catalog) not in (None, getattr(d, a))]
    if isinstance(script.get("world"), dict) and script["world"].get("id") != d.world:
        out.append("world")
    try:
        if opener_of(script) != d.opener:
            out.append("opener")
        if not cadence_ok(script, d.pace, catalog):
            out.append("cadence")
    except (KeyError, IndexError, TypeError):
        pass
    return out


def should_enforce(prompt, d):
    """Enforce every axis on a vague prompt for a rolled direction; pins are enforced regardless."""
    from engine.director.intent import is_vague
    return is_vague(prompt) and getattr(d, "source", "interim") != "interim"


def enforce_direction(script, d, catalog, enforce):
    issues = []
    for axis in drift(script, d, catalog):
        on = enforce or axis in d.pinned or (axis == "cadence" and "pace" in d.pinned)
        if not on:
            issues.append(Issue("direction_drift", axis, f"script differs from the direction on {axis}", "info"))
            continue
        if axis == "mood":
            grade = script.get("grade")
            if not isinstance(grade, dict) or grade.get("id") != "mood_grade":
                script["grade"] = {"id": "mood_grade", "params": {"preset": d.mood}}
            else:
                if not isinstance(grade.get("params"), dict):
                    grade["params"] = {}
                grade["params"]["preset"] = d.mood
            issues.append(Issue("direction_enforced", "grade", f"mood -> {d.mood}", "repaired"))
        elif axis in ("pace", "tone"):
            key, param, bid = _PATHS[axis]
            ref = script.get(key)
            if isinstance(ref, dict) and ref.get("id") == bid:
                if not isinstance(ref.get("params"), dict):
                    ref["params"] = {}
                ref["params"][param] = getattr(d, axis)
                issues.append(Issue("direction_enforced", f"{key}.params.{param}", f"-> {getattr(d, axis)}",
                                    "repaired"))
            elif axis == "pace" and ref is None and script["format"]["durationS"] >= MIN_SEQ_S:
                script["edit"] = {"id": "sequence", "params": {"pace": d.pace}}   # absent edit -> add it
                issues.append(Issue("direction_enforced", "edit", f"added sequence pace {d.pace}", "repaired"))
            elif axis == "tone":
                issues.append(Issue("direction_drift", axis, "world has no tone to set", "info"))
        elif axis == "cadence":
            continue                              # judged after pace is set, below
        else:
            issues.append(Issue(f"direction_{axis}", axis,
                                f"use {axis} '{getattr(d, axis)}' as the job's direction asks", "error"))
    try:
        if (enforce or "pace" in d.pinned) and not cadence_ok(script, d.pace, catalog):
            lo, hi = cadence_range(d.pace, script["format"]["durationS"], catalog)
            issues.append(Issue("direction_cadence", "shots",
                                f"a {d.pace} pace needs {lo}-{hi} shots in this duration", "error"))
    except (KeyError, TypeError):
        pass
    return script, issues
