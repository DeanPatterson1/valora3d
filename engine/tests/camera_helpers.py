"""TEST ONLY helpers for the phase-5 cameras (Chunk 6)."""
import copy
import json
from pathlib import Path

from engine.catalog import Catalog

FIX = Path(__file__).parent / "fixtures"
T3 = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))
CAT = Catalog.load()


def defaults(bid, cat=CAT):
    return {k: v["default"] for k, v in cat.get("camera", bid)["params"].items()}


def sample(bid, cat=CAT):
    return cat.load_camera_path(bid)


def path_module(bid, cat=CAT):
    """The camera's path.py module (helpers beyond sample())."""
    cat.load_camera_path(bid)
    return cat._module_objs[("camera", bid, "path.py")]


def shot(bid, params=None, start=0.0, end=3.0, purpose="motion"):
    return {"startS": start, "endS": end, "purpose": purpose, "focus": "subject",
            "camera": {"id": bid, "params": dict(params or {})}}


def script_with(bid, params=None, index=2, world=None, lighting=None, motion=None):
    """script_t3 with shot `index` on this camera (and optionally another world / lighting / motion)."""
    s = copy.deepcopy(T3)
    s["shots"][index]["camera"] = {"id": bid, "params": dict(params or {})}
    if world:
        s["world"] = {"id": world, "params": {}}
    if lighting:
        s["lighting"] = {"id": lighting, "params": {}}
    if motion:
        s["subject"]["motion"] = {"id": motion[0], "params": dict(motion[1])}
    return s


def bearing_rate(bid, profile, params=None, seconds=3.0, cat=CAT):
    """T3-14 on one shot of this camera at default params (the craft rule's own measure), deg/s."""
    from engine.craft_rules import max_arc_rate
    from engine.script import validate_and_repair
    sh = shot(bid, params, 0.0, seconds)
    s = copy.deepcopy(T3)
    s["shots"] = [sh]
    s = validate_and_repair(s, cat)[0]
    return max_arc_rate(s["shots"][0], profile, cat)
