"""Stage 2 of spec §3: the job's direction. Order:
1. 'more like this': keep a validated direction with a new seed, so only layer 1 changes;
2. the dice: pins from the prompt, history rotated over the viable pool, dislikes avoided, the floor
   enforced;
3. the interim direction with the prompt's pins applied (pins are never dropped).
Pure: the caller holds the memory lock and reads/writes memory (pipeline.py).
Replay never comes here: replay() returns the saved checked script (no provider call)."""
import json
from dataclasses import dataclass

from engine.director.axes import axis_values, validate_axes
from engine.director.baseline_phase3 import profile_key
from engine.director.dice import candidates, roll
from engine.director.direction import AXES, Direction, direction_of, interim_direction, parse_id
from engine.director.family import family
from engine.director.floor import make_viable
from engine.director.pins import read_direction_pins
from engine.director.taste import STATS

REPLAY_SCHEMA = "valora.replay/1"
FLAG_NOTES = {"avoid_relaxed": "every option was on your 'less like this' list; relaxed it to find one",
              "repeat_after_rotation": "every direction for this model has been used once; starting a new round"}


class DirectionIncompatible(ValueError):
    """A 'more like this' / 'less like this' request this model or catalog cannot honour (plain words)."""


@dataclass(frozen=True)
class Choice:
    direction: Direction
    notes: tuple = ()
    flags: tuple = ()


def subject_key(profile):
    return profile_key(profile)


def _load_stats():
    try:
        return json.loads(STATS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def prompt_pins(prompt, profile, catalog, fmt):
    known = axis_values(profile, catalog, fmt, rollable=False)
    return {a: v for a, v in read_direction_pins(prompt).items() if v in known[a]}


def like_axes(like, profile, catalog, fmt):
    """The axes of a 'more like this' reference: a Direction, a direction id, a saved script or result
    ({"direction": {"id": ...}}), or {"id": ...}. Every value must be one this subject knows."""
    try:
        if isinstance(like, Direction):
            axes = like.axes()
        elif isinstance(like, dict):
            axes = parse_id((like.get("direction") or like)["id"])
        else:
            axes = parse_id(like)
    except (KeyError, TypeError, ValueError):
        raise DirectionIncompatible("that 'more like this' reference can't be used for this model: "
                                    "it is not a saved direction") from None
    bad = validate_axes(axes, profile, catalog, fmt)
    if bad:
        raise DirectionIncompatible(f"that direction can't be used for this model: {', '.join(bad)} "
                                    "is not available here")
    return axes


def check_avoid(avoid, profile, catalog, fmt):
    if not avoid:
        return None
    if not isinstance(avoid, dict) or any(not isinstance(v, (list, tuple)) for v in avoid.values()):
        raise DirectionIncompatible("'less like this' must name values per axis, e.g. mood: [clean]")
    known = axis_values(profile, catalog, fmt, rollable=False)
    bad = [f"{a}={v}" for a, vals in avoid.items() for v in vals if a not in AXES or v not in known[a]]
    if bad:
        raise DirectionIncompatible(f"'less like this' names things this model doesn't have: {', '.join(map(str, bad))}")
    return {a: list(v) for a, v in avoid.items() if v}


def _line(d):
    words = f"{d.mood}, {d.pace} pace, {d.tone} backdrop, opens with {d.opener}"
    kept = f"; kept from the prompt: {', '.join(d.pinned)}" if d.pinned else ""
    return f"dice direction: {words}{kept}"


def choose_direction(prompt, profile, catalog, seed, fmt, *, job=None, like=None, avoid=None, history=(),
                     stats=None):
    pins = prompt_pins(prompt, profile, catalog, fmt)
    avoid = check_avoid(avoid, profile, catalog, fmt)
    viable = make_viable(job, profile, catalog) if job is not None else None
    if like is not None:
        axes = {**like_axes(like, profile, catalog, fmt), **pins}
        if viable is not None and not viable(axes):
            raise DirectionIncompatible("that direction doesn't meet the quality bar for this model; "
                                        "try 'new direction' instead")
        d = direction_of(axes, "more_like_this", pinned=pins)
        return Choice(d, (f"more like this: kept the direction ({d.mood}, {d.pace} pace); only details change",))
    r = roll(seed, axis_values(profile, catalog, fmt), pins=pins, history=history, avoid=avoid, viable=viable,
             family_name=family(profile), stats=_load_stats() if stats is None else stats)
    if r.axes is None:
        base = parse_id(interim_direction(seed, profile, catalog).id)
        d = direction_of({**base, **pins}, "interim", pinned=pins)
        return Choice(d, ("no rolled direction met the quality floor; used the default direction",), r.flags)
    d = direction_of(r.axes, "dice", pinned=pins)
    return Choice(d, (_line(d),) + tuple(FLAG_NOTES[f] for f in r.flags if f in FLAG_NOTES), r.flags)


def reachable(profile, catalog, fmt, job=None, prompt=""):
    """Catalog-size honesty (spec §6 'honest limit') for THIS prompt: the same pins, format and
    viability rules the dice use."""
    pins = prompt_pins(prompt, profile, catalog, fmt)
    vals = axis_values(profile, catalog, fmt)
    cands = candidates(vals, pins)
    out = {"pins": pins, "perAxis": vals, "combinations": len(cands),
           "singleValued": [a for a in AXES if a not in pins and len(vals[a]) == 1]}
    if job is not None:
        v = make_viable(job, profile, catalog)
        out["viable"], out["floor"] = sum(1 for c in cands if v(c)), v.floor
    n = out.get("viable", out["combinations"])
    out["distinctBeforeRepeat"] = n
    out["note"] = (f"{n} distinct directions for this model and prompt; axes with one value: "
                   f"{', '.join(out['singleValued']) or 'none'}. Perceived variety is capped by the catalog.")
    return out
