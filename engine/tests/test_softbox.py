import json
import math
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.geometry import point_in_box
from engine.profile import SubjectProfile
from engine.softbox import softbox_layout

FIX = Path(__file__).parent / "fixtures"
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))
P = {k: v["default"] for k, v in Catalog.load().get("lighting", "softbox_three_point")["params"].items()}


def test_key_is_offset_from_the_hero_camera_and_all_lights_clear_the_subject():
    rig = softbox_layout(CAR, (10.0, 0.0, 1.0), P)  # hero camera on +x
    key = next(l for l in rig.lights if l.role == "key")
    assert math.degrees(math.atan2(key.center[1], key.center[0])) == pytest.approx(P["keyAzimuthDeg"], abs=1e-6)
    assert {l.role for l in rig.lights} == {"key", "fill", "rim"}
    assert all(not point_in_box(l.center, CAR.boundsMin, CAR.boundsMax, 0.10) for l in rig.lights)
