"""Review chunk5 #7: a drive never plays in a world without a drive lane (the studio), however short."""
from engine.checker import check
from engine.tests.motion_helpers import CAT, script
from engine.tests.test_director_package import _p


def test_a_slow_short_drive_is_refused_in_the_studio():
    assert CAT.get("world", "studio_cyc")["driveLaneM"] == 0.0
    s = script("drive", {"speedKmh": 5.0, "driveS": 1.0, "facing": "forward"}, world="studio_cyc")
    r = check(s, _p("sports_car"), CAT)                  # +-0.69 m: inside the generic 0.91 m travel allowance
    errs = [i for i in r.issues if i.severity == "error"]
    assert not r.ok and [i.code for i in errs] == ["path_through_world"], [(i.code, i.message) for i in r.issues]
    assert "drive lane" in errs[0].message
