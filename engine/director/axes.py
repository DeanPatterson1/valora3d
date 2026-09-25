"""Dice axes (spec §6 layer 2): which values this subject and format may roll. Values come from the
catalog (worlds, grade presets, selectable cameras) intersected with dice.json, so the dice can never
pick something the menu does not offer: every catalog-backed axis (world, mood, tone, pace, opener) is
the catalog's own enum, narrowed by dice.json, so a value the catalog drops stops being rollable. Weather
and wind have no catalog block yet (phase 5), so they come from dice.json alone and only dry/calm roll.
Harness-only blocks (turntable) are not selectable and so are never values."""
import json
from pathlib import Path

from engine.director.direction import AXES
from engine.director.family import family

DICE_FILE = Path(__file__).with_name("dice.json")


def load_dice(path=DICE_FILE):
    return json.loads(path.read_text(encoding="utf-8"))


DICE = load_dice()
TONE_NA = DICE.get("toneNA", "na")   # the tone of a world without a toneParam (Task 73): no new axis, no new id


def tone_values(world_manifest):
    """The tone values a world offers: its toneParam's enum, or the single value 'na' (tone does not apply)."""
    tp = (world_manifest or {}).get("toneParam")
    return list(world_manifest["params"][tp]["values"]) if tp else [TONE_NA]


def tone_fits_world(axes, catalog):
    """A tone only pairs with the world that offers it ('na' only with a tone-less world)."""
    w = catalog.get("world", axes.get("world")) if catalog is not None else None
    return w is None or axes.get("tone") in tone_values(w)


def _world_ok(m, profile, fmt):
    lo, hi = m["subjectSizeM"]
    return lo <= profile.longest <= hi and fmt["aspect"] in m["aspects"]


def _opener_ok(m):
    """An opener is a full-framing hook (a detail camera cannot open: seq_bad_hook) that can reach T3 (a
    T1-capped camera such as the turntable control can never meet the quality floor), on top of being
    director-selectable. A camera that is not full-frame from its first frame declares hookable false (reveal_rise
    starts on a detail, Task 80)."""
    return (m.get("framing") == "full" and m.get("tierMax", "T3") == "T3" and not m.get("constantSpeed")
            and m.get("hookable", True))


def axis_values(profile, catalog, fmt, dice=None, rollable=True):
    """{axis: [values]}. rollable=False lists every value an axis knows: prompt pins and 'more like
    this' may use them, the dice may not (noir, rain, windy)."""
    dice = dice or DICE
    rare = set(dice["rare"].get("mood", [])) if rollable else set()
    cams = {c for c in catalog.selectable_ids("camera") if _opener_ok(catalog.get("camera", c))}
    paces = catalog.get("edit", "sequence")["params"]["pace"]["values"]
    pace = [x for x in dice["paceByFamily"][family(profile)] if x in paces] if rollable else paces
    worlds = [w for w in catalog.selectable_ids("world") if _world_ok(catalog.get("world", w), profile, fmt)
              and (not rollable or w in dice.get("worlds", [w]))]           # dice.json worlds: removed in Task 87
    tones = []
    for w in worlds or ["studio_cyc"]:   # tone per world (Task 73); candidates() pairs each world with its own
        tones += [t for t in tone_values(catalog.get("world", w)) if t not in tones]
    out = {
        "world": worlds,
        "mood": [m for m in catalog.get("grade", "mood_grade")["params"]["preset"]["values"] if m not in rare],
        "tone": tones,
        "pace": list(pace),
        "opener": [c for c in dice["openers"] if c in cams],
        "weather": list(dice["weather"]["rollable" if rollable else "values"]),
        "wind": list(dice["wind"]["rollable" if rollable else "values"]),
    }
    return {a: out[a] for a in AXES}


def compatible(axes, dice=None, catalog=None):
    """Tone must be one the world offers (with a catalog: 'na' exactly for a tone-less world, Task 73) and
    suit the mood (dice.json toneByMood). Everything else combines freely."""
    if not tone_fits_world(axes, catalog):
        return False
    if axes["tone"] == TONE_NA:
        return True                     # no backdrop tone, no mood rule to meet
    table = (dice or DICE)["toneByMood"]
    return axes["tone"] in table.get(axes["mood"], [axes["tone"]])


def opener_of(script):
    """The opener a script actually uses: the first shot's camera (openers are full-framing hooks)."""
    return script["shots"][0]["camera"]["id"]


def validate_axes(axes, profile, catalog, fmt):
    """Axes whose value this subject/format does not know (rollable=False values). [] means valid. Used
    for 'more like this' and for memory writes, so no unknown or free-text value is ever accepted."""
    if not isinstance(axes, dict):
        return list(AXES)
    known = axis_values(profile, catalog, fmt, rollable=False)
    bad = [a for a in AXES if axes.get(a) not in known[a]]
    if "tone" not in bad and "world" not in bad and not tone_fits_world(axes, catalog):
        bad.append("tone")              # a known tone on the wrong world ('na' in the studio, 'white' at night)
    return [a for a in AXES if a in bad]
