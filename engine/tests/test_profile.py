import json
from pathlib import Path

import pytest

from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"


def test_round_trip_and_derived_values():
    raw = json.loads((FIX / "profile_car.json").read_text())
    p = SubjectProfile.from_dict(raw)
    assert p.to_dict() == raw
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
