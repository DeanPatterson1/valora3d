import json

import pytest

from engine.ingest.run import _extract, ingest
from engine.tests.blender_fixtures import make_glb
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]


def _raw(kind, tmp_path):
    glb = make_glb(kind, tmp_path / f"{kind}.glb")
    _extract(glb, tmp_path)  # writes raw.json next to it
    return json.loads((tmp_path / "raw.json").read_text(encoding="utf-8"))


def test_raw_carries_islands_sample_origins_and_part_objects(tmp_path):
    raw = _raw("wheeled", tmp_path)
    assert all(len(r) == 12 for r in raw["samples"])            # [.., curv, open, obj, island]
    objs = {int(r[10]) for r in raw["samples"]}
    assert len(objs) >= 9                                        # body + 4 tyres + 4 rims (+ calipers)
    assert all(int(r[11]) >= 0 for r in raw["samples"])
    assert all({"obj", "id", "n", "lo", "hi", "centroid"} <= set(i) for i in raw["islands"])
    assert len(raw["islands"]) >= 13                             # every separate piece is one island
    assert all("obj" in p for p in raw["parts"])


def test_wheeled_fixture_yields_four_separable_tyres_and_a_sport_body(tmp_path):
    p = ingest(make_glb("wheeled", tmp_path / "w.glb"), workdir=tmp_path / "x")
    assert len(p.wheels) == 4 and all(w["confidence"] == "high" for w in p.wheels)
    for w in p.wheels:
        assert w["separable"] is True and 0.5 <= w["tyreBand"][0] <= 0.7 and 0.08 <= w["width"] <= 0.16
    assert p.vehicle["bodySeparable"] is True and p.vehicle["vehicleClass"] == "sport"
    assert p.softParts == [] or all(s["confidence"] == "low" for s in p.softParts)


def test_strap_fixture_yields_one_high_confidence_dangling_part(tmp_path):
    p = ingest(make_glb("strap", tmp_path / "s.glb"), workdir=tmp_path / "x")
    high = [d for d in p.danglingParts if d["confidence"] == "high"]
    assert len(high) == 1 and high[0]["pivot"][2] > high[0]["tip"][2]


def test_plush_fixture_is_soft_and_touches_the_ground(tmp_path):
    p = ingest(make_glb("plush", tmp_path / "p.glb"), workdir=tmp_path / "x")
    assert [s["confidence"] for s in p.softParts] == ["high"] and p.softParts[0]["touchesGround"]
    assert len(p.groundContacts) == 1 and p.wheels == []
