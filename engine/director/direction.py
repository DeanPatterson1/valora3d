"""A direction: what the dice rolled for one job (spec §6 layer 2). Seven axes, in a fixed order, so a
direction id round-trips and any job can be replayed from its script. interim_direction (phase 3) is
kept as the last resort when the dice find nothing viable. Moods come from the catalog's mood_grade
presets, so they cannot drift."""
import random
from dataclasses import dataclass

from engine.director.family import family

AXES = ("world", "mood", "tone", "pace", "opener", "weather", "wind")
AXIS_DEFAULTS = {"world": "studio_cyc", "opener": "low_hero_push", "weather": "dry", "wind": "calm"}

TONE = {"premium_dark": "black", "teal_night": "black", "noir": "black", "clean": "white",
        "warm_golden": "grey", "vivid": "grey"}
PACES = {"vehicle": ("medium", "hype"), "product": ("calm", "medium", "hype"),
         "furniture": ("calm",), "character": ("calm", "medium")}
RARE = ("noir",)  # mood_grade: "use rarely" -> never rolled; a prompt can still ask for it
# Frozen phase-3 inputs (phase 5 Task 51): the interim direction must not change when the catalog grows.
# These are the mood_grade presets at the frozen revision, in catalog order, minus RARE.
PHASE3_MOODS = ("clean", "premium_dark", "warm_golden", "teal_night", "vivid")


@dataclass(frozen=True)
class Direction:
    id: str
    mood: str
    pace: str
    tone: str
    source: str = "interim"          # interim | dice | more_like_this | replay
    world: str = "studio_cyc"
    opener: str = "low_hero_push"
    weather: str = "dry"
    wind: str = "calm"
    pinned: tuple = ()               # axes the prompt pinned (sorted names)

    def axes(self):
        return {a: getattr(self, a) for a in AXES}

    @classmethod
    def from_script(cls, script):
        return direction_of(parse_id(script["direction"]["id"]), "replay")


def make_id(axes):
    return "/".join(axes[a] for a in AXES)


def parse_id(s):
    """7-part ids (phase 4) or legacy 3-part mood/pace/tone ids (phase 3). Anything else: ValueError."""
    if not isinstance(s, str):
        raise ValueError("direction id must be text")
    parts = s.split("/")
    if any(not p for p in parts):
        raise ValueError(f"bad direction id {s!r}")
    if len(parts) == len(AXES):
        return dict(zip(AXES, parts))
    if len(parts) == 3:
        mood, pace, tone = parts
        return {**AXIS_DEFAULTS, "mood": mood, "pace": pace, "tone": tone}
    raise ValueError(f"bad direction id {s!r}")


def direction_of(axes, source, pinned=()):
    return Direction(id=make_id(axes), mood=axes["mood"], pace=axes["pace"], tone=axes["tone"], source=source,
                     world=axes["world"], opener=axes["opener"], weather=axes["weather"], wind=axes["wind"],
                     pinned=tuple(sorted(pinned)))


def interim_direction(seed, profile, catalog):
    known = set(catalog.get("grade", "mood_grade")["params"]["preset"]["values"])
    moods = [v for v in PHASE3_MOODS if v in known]   # frozen order; a dropped preset still drops out
    rng = random.Random(f"direction:{seed}")
    mood = rng.choice(moods)
    pace = rng.choice(PACES[family(profile)])
    tone = TONE.get(mood, "grey")
    return Direction(f"{mood}/{pace}/{tone}", mood, pace, tone)
