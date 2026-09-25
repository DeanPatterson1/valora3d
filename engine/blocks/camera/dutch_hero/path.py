"""dutch_hero (phase 5 Task 81): the low_hero_push maths plus a camera roll of rollDeg about the view axis.

rollSide is a param, not a seeded draw, so replay is exact: "right" tilts the picture's top to the right
(an upright line through the target leans with its top to screen-right under geometry.project:
Pose.roll = +rollDeg), "left" the other way. The roll is
constant over the shot (a dutch angle, not a roll move); geometry.project and camera_matrix apply it, so the
checker's framing and the compiled camera agree. The low hero push is loaded from this catalog root's own
sibling block (never a same-named module another catalog root loaded)."""
import importlib.util
import math
from dataclasses import replace
from pathlib import Path

_HERO = None


def _hero():
    global _HERO
    if _HERO is None:
        f = Path(__file__).resolve().parent.parent / "low_hero_push" / "path.py"
        spec = importlib.util.spec_from_file_location(f"valora_dutch_low_hero_{abs(hash(str(f)))}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _HERO = mod.sample
    return _HERO


def roll_rad(params):
    return (1.0 if params["rollSide"] == "right" else -1.0) * math.radians(params["rollDeg"])


def sample(params, profile, u, target=None):
    return replace(_hero()(params, profile, u, target), roll=roll_rad(params))
