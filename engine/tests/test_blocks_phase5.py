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
