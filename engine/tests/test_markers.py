import copy
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.markers import gltf_to_placed
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))
BASE = json.loads((FIX / "script_valid.json").read_text())


def _script(markers):
    s = copy.deepcopy(BASE)
    s["markers"] = markers
    return s


def _m(**kw):
    m = {"id": "m1", "anchor": {"space": "placed", "point": list(CAR.center)}, "text": "glint here"}
    m.update(kw)
    return m


def _codes(r, sev="error"):
    return {i.code for i in r.issues if i.severity == sev}


def test_valid_marker_passes():
    r = check(_script([_m(timeS=3.0)]), CAR, CAT)
    assert r.ok, [i.to_dict() for i in r.issues]


@pytest.mark.parametrize("marker,code", [
    ("not-a-dict", "bad_marker"),
    (_m(id="Bad Id"), "bad_marker_id"),
    (_m(text=""), "bad_marker_text"),
    (_m(text="x" * 281), "bad_marker_text"),
    (_m(text="bell\x07"), "bad_marker_text"),
    (_m(anchor={"space": "placed", "point": [0, 0]}), "bad_marker_anchor"),
    (_m(anchor={"space": "placed", "point": [0, float("nan"), 0]}), "bad_marker_anchor"),
    (_m(anchor={"space": "screen", "point": [0, 0, 0]}), "bad_marker_anchor"),
    (_m(anchor={"space": "placed", "point": [0, 0, 0.5], "normal": [0, 0, 0]}), "bad_marker_anchor"),
    (_m(timeS=99), "bad_marker_time"),
    (_m(extra=1), "bad_marker"),
])
def test_malformed_markers_are_errors_not_crashes(marker, code):
    r = check(_script([marker]), CAR, CAT)
    assert not r.ok and code in _codes(r)


def test_duplicate_ids_and_too_many():
    assert "duplicate_marker_id" in _codes(check(_script([_m(), _m()]), CAR, CAT))
    many = [_m(id=f"m{i}") for i in range(9)]
    assert "too_many_markers" in _codes(check(_script(many), CAR, CAT))


def test_marker_off_the_subject_is_an_error():
    far = _m(anchor={"space": "placed", "point": [50.0, 0.0, 0.5]})
    assert "marker_off_subject" in _codes(check(_script([far]), CAR, CAT))


def test_gltf_point_is_converted_to_placed():
    # glTF (x, y, z) -> Blender (x, -z, y), then (v - (cx, cy, minZ)) * f.
    prof = SubjectProfile.from_dict({**CAR.to_dict(), "sourceCenter": [1.0, 2.0, 0.0],
                                     "sourceMinZ": -0.5, "scaleFactor": 0.01})
    assert gltf_to_placed([10.0, 20.0, -30.0], prof) == pytest.approx([0.09, 0.28, 0.205])
    placed = list(CAR.center)
    gltf = [placed[0], placed[2], -placed[1]]  # inverse of the importer axis swap (identity placement)
    r = check(_script([_m(anchor={"space": "gltf", "point": gltf})]), CAR, CAT)
    assert r.ok and "marker_converted" in _codes(r, "repaired")
    assert r.script["markers"][0]["anchor"] == {"space": "placed", "point": pytest.approx(placed)}
