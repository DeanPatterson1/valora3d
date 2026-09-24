import json
from pathlib import Path
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"


def test_round_trip_and_derived_values():
    raw = json.loads((FIX / "profile_car.json").read_text())
    p = SubjectProfile.from_dict(raw)
    assert p.to_dict() == raw
    assert p.center == (0.0, 0.0, 0.65)
    assert abs(p.radius - (2.25**2 + 0.95**2 + 0.65**2) ** 0.5) < 1e-9
    assert p.longest == 4.5
