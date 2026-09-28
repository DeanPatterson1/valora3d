"""Phase 6 Task 95: pure sim facts (containers, fill lines, emitters, nose sign, pile zone). Markers first,
then the measured shape (PHASING §2). No SubjectProfile field is added: profile_key stays unchanged."""
import dataclasses
import json
import math
from pathlib import Path

import pytest

from engine.physics import shape
from engine.physics.sim_facts import container, emitters, fill_line, nose_sign, pile_zone
from engine.profile import SubjectProfile
from engine.tests.test_director_package import _p

SYN = Path(__file__).parent / "fixtures" / "synthetic_profiles"


def _syn(name):
    return SubjectProfile.from_dict(json.loads((SYN / f"{name}.json").read_text(encoding="utf-8")))


def _marker(mid, text, point, normal=None):
    a = {"space": "placed", "point": list(point)}
    if normal:
        a["normal"] = list(normal)
    return {"id": mid, "text": text, "anchor": a}


# --- container -----------------------------------------------------------------------------------------------

def test_a_rim_marker_is_a_confident_opening():
    p = _syn("bottle")
    c = container(p, [_marker("m1", "pour into the mouth", [0.0, 0.0, 0.26])])
    assert c["confidence"] == "high" and c["opening"] == [0.0, 0.0, 0.26]
    assert c["radiusM"] == pytest.approx(0.035, rel=0.1)


def test_an_upright_round_top_is_a_low_confidence_opening():
    p = _syn("bottle")
    c = container(p, [])
    assert c["confidence"] == "low"
    assert c["opening"][2] == pytest.approx(p.boundsMax[2])
    assert c["radiusM"] == pytest.approx(0.035, rel=0.1)


def test_a_can_on_its_side_has_no_opening():
    assert container(_syn("can"), []) is None


def test_an_unrelated_marker_is_ignored():
    assert container(_syn("can"), [_marker("m1", "the logo", [0.0, 0.0, 0.03])]) is None


# --- fill line -----------------------------------------------------------------------------------------------

def test_fill_line_marker_first_then_the_full_default():
    p = _syn("bottle")
    f = fill_line(p, [_marker("f", "fill line", [0.035, 0.0, 0.2])])
    assert (f["z"], f["confidence"], f["source"]) == (0.2, "high", "marker")
    d = fill_line(p, [])
    assert d["z"] == pytest.approx(0.85 * 0.26) and d["confidence"] == "low" and d["level"] == "full"


# --- emitters ------------------------------------------------------------------------------------------------

def test_emitters_markers_first_then_emissive_detail_points():
    p = _p("sneaker")
    p = dataclasses.replace(p, detailPoints=list(p.detailPoints) + [
        {"kind": "emissive", "point": [0.01, 0.02, 0.03], "normal": [0, 0, 1], "score": 3.0}])
    e = emitters(p, [_marker("x", "smoke from the exhaust", [0.1, 0.0, 0.02], [0, -1, 0])])
    assert e[0]["source"] == "marker:x" and e[0]["confidence"] == "high" and e[0]["normal"] == [0, -1, 0]
    assert e[1]["source"].startswith("detail:") and e[1]["point"] == [0.01, 0.02, 0.03]
    assert e[1]["confidence"] == "medium"
    assert emitters(_p("sneaker"), []) == [] or all(x["source"].startswith("detail:") for x in emitters(_p("sneaker"), []))


# --- nose sign -----------------------------------------------------------------------------------------------

def test_a_front_marker_sets_a_confident_nose_sign():
    p = _p("sports_car")
    ax = p.vehicle["forwardAxis"]
    i = max(range(3), key=lambda j: abs(ax[j]))
    back = list(p.center)
    back[i] -= math.copysign(0.4 * p.sizeM[i], ax[i])          # a point at the rear along the forward axis
    sign, conf = nose_sign(p, [_marker("n", "the nose", back)])
    assert conf == "high" and sign == -int(math.copysign(1, ax[i]))


def test_without_markers_nose_sign_defers_to_the_shape():
    p = _p("sports_car")
    assert nose_sign(p, []) == shape.nose_sign(p)


# --- pile zone -----------------------------------------------------------------------------------------------

def test_pile_zone_is_a_ground_annulus_outside_the_footprint():
    p = _p("sneaker")
    r = math.hypot(p.half[0], p.half[1])
    z = pile_zone(p)
    assert z["center"] == [pytest.approx(p.center[0]), pytest.approx(p.center[1]), 0.0]
    assert z["innerM"] == pytest.approx(1.05 * r) and z["outerM"] == pytest.approx(1.6 * r)


def test_sim_facts_add_no_profile_field():
    fields = {f.name for f in dataclasses.fields(SubjectProfile)}
    assert not fields & {"container", "fillLine", "emitters", "pileZone", "noseSign"}
