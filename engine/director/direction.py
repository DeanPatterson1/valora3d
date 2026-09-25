"""Interim direction (phase 3). Phase 4 replaces it with the dice + variety memory (spec §6); the
Direction shape stays. Moods come from the catalog's mood_grade presets, so they cannot drift."""
import random
from dataclasses import dataclass

from engine.director.family import family

TONE = {"premium_dark": "black", "teal_night": "black", "noir": "black", "clean": "white",
        "warm_golden": "grey", "vivid": "grey"}
PACES = {"vehicle": ("medium", "hype"), "product": ("calm", "medium", "hype"),
         "furniture": ("calm",), "character": ("calm", "medium")}
RARE = ("noir",)  # mood_grade: "use rarely" -> never rolled; a prompt can still ask for it


@dataclass(frozen=True)
class Direction:
    id: str
    mood: str
    pace: str
    tone: str
    source: str = "interim"


def interim_direction(seed, profile, catalog):
    moods = [v for v in catalog.get("grade", "mood_grade")["params"]["preset"]["values"] if v not in RARE]
    rng = random.Random(f"direction:{seed}")
    mood = rng.choice(moods)
    pace = rng.choice(PACES[family(profile)])
    tone = TONE.get(mood, "grey")
    return Direction(f"{mood}/{pace}/{tone}", mood, pace, tone)
