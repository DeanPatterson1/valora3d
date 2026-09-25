"""Direction pins read from the prompt (spec §6: an explicit request beats the dice). The phrases are
data (dice.json "pins"). Per axis, the first mention in reading order wins. A negated mention ('no
neon', 'without quick cuts') is not a pin; the negation rule is the same one capability detection uses.
Deterministic: what the prompt pinned is never left to the LLM."""
import re

from engine.director.axes import DICE
from engine.director.capabilities import _negated


def compile_pins(dice=None):
    table = (dice or DICE)["pins"]
    return {axis: [(value, re.compile(r"\b(?:" + "|".join(ph) + r")\b", re.I)) for value, ph in vals.items()]
            for axis, vals in table.items()}


_PINS = compile_pins()


def read_direction_pins(prompt, pins=None):
    text, out = prompt or "", {}
    for axis, table in (pins or _PINS).items():
        best = None
        for value, rx in table:
            for m in rx.finditer(text):
                if _negated(text, m):
                    continue
                if best is None or m.start() < best[0]:
                    best = (m.start(), value)
                break
        if best:
            out[axis] = best[1]
    return out
