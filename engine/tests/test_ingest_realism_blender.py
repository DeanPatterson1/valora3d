import json

import pytest

from engine.ingest.run import _extract
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
