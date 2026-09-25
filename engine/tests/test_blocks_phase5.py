"""Block recipe step 1: every phase-5 block's manifest against its task's table (plan chunks 2-6).
New blocks land directorSelectable false and are flipped in Task 88 (review amendment 63->88)."""
from engine.catalog import Catalog


def _m(kind, bid):
    m = Catalog.load().get(kind, bid)
    assert m is not None, f"{kind}/{bid} missing"
    return m


def _param(m, name, typ, default, lo=None, hi=None, values=None):
    p = m["params"][name]
    assert p["type"] == typ and p["default"] == default, (name, p)
    if lo is not None:
        assert (p["min"], p["max"]) == (lo, hi), (name, p)
    if values is not None:
        assert p["values"] == values, (name, p)


def test_ground_fog_manifest():                                     # Task 60
    m = _m("effect", "ground_fog")
    _param(m, "heightM", "number", 0.4, 0.1, 1.5)
    _param(m, "density", "number", 0.4, 0.0, 1.0)
    _param(m, "mode", "enum", "fog", values=["fog", "mist"])
    _param(m, "tint", "enum", "neutral", values=["neutral", "warm", "cool"])
    assert m["physics"] == {"taxonomy": ["GS-04"], "state": "stateless", "windDriven": True,
                            "windCalibration": {"unit": "drift m/s", "perMs": 0.5},
                            "requiresWorld": {"hasGround": True}}
    assert m["atmosphere"] is True and m["maxPerClip"] == 1 and m["costWeight"] == 2.0
    assert m["tierMax"] == "T3" and m["subjectSizeM"] == [0.05, 30.0]
    assert m["capabilities"] == ["atmosphere.fog"]
    assert m["tags"]["mood"] == ["moody", "night", "mysterious"] and m["tags"]["energy"] == ["calm", "medium"]
    assert m.get("directorSelectable") is False                     # flipped in Task 88


def test_rain_courtyard_manifest():                                 # Task 63 (+ amendments 63, 63->88)
    m = _m("world", "rain_courtyard")
    _param(m, "wetness", "number", 0.0, 0.0, 1.0)
    _param(m, "timeOfDay", "enum", "overcast_day", values=["overcast_day", "dusk"])
    _param(m, "dressing", "enum", "full", values=["full", "sparse"])
    facts = {k: m[k] for k in ("hasGround", "groundType", "hasFoliage", "outdoor", "weathers", "temperature",
                               "windDefault", "timeOfDay", "toneParam", "driveLaneM")}
    assert facts == {"hasGround": True, "groundType": "asphalt", "hasFoliage": True, "outdoor": True,
                     "weathers": ["dry", "wet", "rain", "fog"], "temperature": "mild", "windDefault": 0.8,
                     "timeOfDay": {"param": "timeOfDay", "values": ["overcast_day", "dusk"]}, "toneParam": None,
                     "driveLaneM": 24.0}
    assert m["subjectSizeM"] == [0.03, 6.0] and m["costWeight"] == 3.0 and m["tierMax"] == "T3"
    assert m["capabilities"] == ["world.street", "world.nature"]
    assert m["tags"]["mood"] == ["moody", "cinematic", "rainy"] and m["tags"]["palette"] == ["cool"]
    assert m.get("directorSelectable") is False


def test_dice_roll_only_studio_worlds_until_task_87():
    """Amendment 63->88: dice.json 'worlds' keeps new worlds unrollable even once one is selectable."""
    import copy
    from engine.director.axes import DICE, axis_values
    from engine.tests.test_director_package import _p
    cat = Catalog.load()
    grown = copy.copy(cat)
    grown._blocks = copy.deepcopy(cat._blocks)
    grown._blocks[("world", "rain_courtyard")]["directorSelectable"] = True
    fmt = {"aspect": "9:16", "durationS": 10, "fps": 30}
    assert DICE["worlds"] == ["studio_cyc"]
    assert axis_values(_p("sports_car"), grown, fmt)["world"] == ["studio_cyc"]
    assert "rain_courtyard" in axis_values(_p("sports_car"), grown, fmt, rollable=False)["world"]


def test_courtyard_rejects_a_subject_over_6_m():
    import dataclasses
    import json
    from engine.checker import check
    from engine.tests.test_director_package import _p
    from engine.tests.test_growth_floor import T3
    p = _p("sports_car")
    k = 8.0 / p.longest
    big = dataclasses.replace(p, sizeM=[v * k for v in p.sizeM], boundsMin=[v * k for v in p.boundsMin],
                              boundsMax=[v * k for v in p.boundsMax])
    s = json.loads(json.dumps(T3))
    s["world"] = {"id": "rain_courtyard", "params": {}}
    r = check(s, big, Catalog.load())
    assert ("subject_size_unsupported", "world") in {(i.code, i.path) for i in r.issues}
