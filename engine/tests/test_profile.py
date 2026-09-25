import json
from pathlib import Path

import pytest

from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"


def test_round_trip_and_derived_values():
    raw = json.loads((FIX / "profile_car.json").read_text())
    p = SubjectProfile.from_dict(raw)
    d = p.to_dict()
    assert {k: d[k] for k in raw} == raw
    assert p.center == (0.0, 0.0, 0.65)
    assert abs(p.radius - (2.25**2 + 0.95**2 + 0.65**2) ** 0.5) < 1e-9
    assert p.longest == 4.5


def test_from_dict_missing_key_raises_value_error():
    raw = json.loads((FIX / "profile_car.json").read_text())
    del raw["sizeM"]
    with pytest.raises(ValueError):
        SubjectProfile.from_dict(raw)


def test_from_dict_unknown_key_raises_value_error():
    raw = json.loads((FIX / "profile_car.json").read_text())
    raw["bogusKey"] = 1
    with pytest.raises(ValueError):
        SubjectProfile.from_dict(raw)


def test_older_profile_without_placement_loads_with_identity_placement():
    raw = json.loads((FIX / "profile_car.json").read_text())
    assert "sourceCenter" not in raw
    p = SubjectProfile.from_dict(raw)
    assert p.sourceCenter == [0.0, 0.0, 0.0]
    assert p.sourceMinZ == 0.0 and p.scaleFactor == 1.0


def test_placement_round_trips():
    raw = json.loads((FIX / "profile_car.json").read_text())
    raw.update(sourceCenter=[3250.0, 0.0, 850.0], sourceMinZ=200.0, scaleFactor=0.001)
    d = SubjectProfile.from_dict(raw).to_dict()
    assert {k: d[k] for k in raw} == raw


def test_new_ingest_fields_default_and_round_trip():
    old = json.loads((FIX / "profile_car.json").read_text())
    p = SubjectProfile.from_dict(old)  # a phase-1 document still loads
    assert (p.glossShare, p.reflectionTargets, p.shoulderLine, p.detailPoints, p.wheels, p.parts,
            p.boundsPosed) == (0.0, [], [], [], [], [], False)
    rich = {**old, "glossShare": 0.4, "boundsPosed": True,
            "reflectionTargets": [{"kind": "top", "point": [0, 0, 1.3], "normal": [0, 0, 1], "area": 3.0}],
            "detailPoints": [{"kind": "emissive", "point": [2.2, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.2}],
            "wheels": [{"center": [1.4, 0.8, 0.33], "radius": 0.33, "axis": [0, 1, 0], "confidence": "high"}],
            "shoulderLine": [{"side": "+y", "points": [[0, 0.95, 0.8]]}],
            "parts": [{"index": 0, "boundsMin": [-1, -1, 0], "boundsMax": [1, 1, 1], "polyShare": 1.0}]}
    d = SubjectProfile.from_dict(rich).to_dict()
    assert {k: d[k] for k in rich} == rich


def _doc():
    return json.loads((FIX / "profile_car.json").read_text())


def test_realism_fields_default_empty_for_older_documents():
    p = SubjectProfile.from_dict(_doc())
    assert p.vehicle == {} and p.groundContacts == [] and p.softParts == [] and p.danglingParts == []


def test_realism_fields_round_trip():
    d = _doc()
    d.update(vehicle={"forwardAxis": [0.0, 1.0, 0.0], "wheelbaseM": 2.5, "trackM": 1.6, "rideHeightM": 0.12,
                      "bodySeparable": True, "vehicleClass": "sport"},
             groundContacts=[{"center": [0.0, 0.0, 0.0], "radius": 0.1, "share": 1.0}],
             softParts=[{"part": 0, "share": 0.9, "touchesGround": True, "confidence": "high"}],
             danglingParts=[{"pivot": [0, 0, 0.3], "tip": [0, 0, 0.15], "radius": 0.005, "lengthM": 0.15,
                             "confidence": "high"}])
    assert SubjectProfile.from_dict(d).to_dict() == SubjectProfile.from_dict(SubjectProfile.from_dict(d).to_dict()).to_dict()
    assert SubjectProfile.from_dict(d).vehicle["vehicleClass"] == "sport"


def test_animation_clips_default_empty_for_older_documents():
    assert SubjectProfile.from_dict(_doc()).animationClips == []
    d = {**_doc(), "animationClips": [{"index": 0, "frameStart": 1.0, "frameEnd": 49.0, "fps": 24.0,
                                        "durationS": 2.0, "nameHint": "Walk"}]}
    assert SubjectProfile.from_dict(d).to_dict()["animationClips"] == d["animationClips"]
