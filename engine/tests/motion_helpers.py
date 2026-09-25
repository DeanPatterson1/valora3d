"""TEST ONLY helpers for the phase-5 motion blocks (Chunk 5)."""
import copy
import json
from pathlib import Path

from engine.catalog import Catalog

FIX = Path(__file__).parent / "fixtures"
T3 = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))
CAT = Catalog.load()


def module(bid, cat=CAT):
    """The block's path.py module (its helpers beyond sample(): heights, windows, rest times)."""
    return cat.motion_module(bid)


def defaults(bid, cat=CAT):
    return {k: v["default"] for k, v in cat.get("motion", bid)["params"].items()}


def script(bid, params=None, duration=10, world=None, lighting=None, placement=None):
    """script_t3 with this motion (and optionally another world / lighting / placement)."""
    s = copy.deepcopy(T3)
    s["format"]["durationS"] = duration
    s["subject"]["motion"] = {"id": bid, "params": dict(params or {})}
    if world:
        s["world"] = {"id": world, "params": {}}
    if lighting:
        s["lighting"] = {"id": lighting, "params": {}}
    if placement:
        s["subject"]["placement"] = placement
    return s


def synthetic(name):
    from engine.profile import SubjectProfile
    return SubjectProfile.from_dict(json.loads((FIX / "synthetic_profiles" / f"{name}.json").read_text(encoding="utf-8")))
