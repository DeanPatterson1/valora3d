import json
from pathlib import Path

from engine.catalog import Catalog
from engine import craft_rules as cr
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))


def _shot(cam, params, start=0.0, end=3.0):
    return {"startS": start, "endS": end, "camera": {"id": cam, "params": {
        **{k: v["default"] for k, v in CAT.get("camera", cam)["params"].items()}, **params}}}


def test_still_tail_measures_the_settle():
    assert cr.still_tail_s(_shot("arc_orbit", {"settleFrac": 0.4}), CAR, CAT) >= 1.0
    assert cr.still_tail_s(_shot("arc_orbit", {"settleFrac": 0.0}), CAR, CAT) < 0.5


def test_thirty_degree_rule():
    a = _shot("arc_orbit", {"startAzimuthDeg": 0, "sweepDeg": 10})
    b = _shot("arc_orbit", {"startAzimuthDeg": 15, "sweepDeg": 10})
    c = _shot("arc_orbit", {"startAzimuthDeg": 60, "sweepDeg": 10})
    assert cr.cut_ok(a, b, CAR, CAT, "9:16")[0] is False
    assert cr.cut_ok(a, c, CAR, CAT, "9:16")[0] is True


def test_anti_miniature_dof_on_vehicles():
    close_wide_open = _shot("low_hero_push", {"distance": 1.5, "lensMm": 50, "fstop": 1.4})
    far_stopped = _shot("low_hero_push", {"distance": 4.0, "lensMm": 50, "fstop": 8.0})
    assert cr.dof_ok(close_wide_open, CAR, CAT, "9:16") is False
    assert cr.dof_ok(far_stopped, CAR, CAT, "9:16") is True


def test_dof_must_cover_both_ends_of_the_subject():
    # Total depth of field is 1.1x the car's depth, but it sits behind focus: the near end blurs.
    sh = _shot("low_hero_push", {"distance": 2.5, "lensMm": 35, "fstop": 2.8})
    assert cr.dof_ok(sh, CAR, CAT, "9:16") is False


def test_score_script_reports_every_s_item():
    s = json.loads((FIX / "script_t3.json").read_text())
    from engine.checker import check
    rich = SubjectProfile.from_dict({**CAR.to_dict(), "detailPoints": [
        {"kind": "emissive", "point": [2.25, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.0}]})
    r = check(s, rich, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    items = {x.id: x for x in cr.score_script(r.script, rich, CAT)}
    for iid in ("T1-X1", "T1-X3", "T2-01", "T2-03", "T2-04", "T2-05", "T2-07", "T3-01", "T3-02",
                "T3-03", "T3-04", "T3-05", "T3-11", "T3-13", "T3-14", "T3-16", "T3-21", "T4-02",
                "T4-03", "V-C02"):
        assert iid in items, iid
    assert items["T3-02"].status == "pass" and items["T3-13"].status == "pass"
    # studio_cyc carries `"studio": true` (owner 2026-09-24: clean studio meets T2-07).
    # Add that key to engine/blocks/world/studio_cyc/block.json in this task; the catalog
    # only rejects MISSING keys, so an extra flag loads fine. Future non-studio worlds omit it.
    assert items["T2-07"].status == "pass"
    assert CAT.get("effect", "haze_volume")["atmosphere"] is True  # T2-07 also met by haze
    assert items["T4-03"].status == "fail"  # no simulation in v1: honest, not n/a
