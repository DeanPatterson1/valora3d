"""Round 13 realism layers, pure: the night street's practicals-only light (no rig, a stray lamp through the side
glass) and the road's mess; the committed scripts' round-13 values."""
import json
import math
from pathlib import Path

from engine.catalog import Catalog
from engine.tests.test_director_package import _p

ROOT = Path(__file__).parents[2]


def _load(s):
    return json.loads((ROOT / "harness" / "realism" / f"{s}.json").read_text(encoding="utf-8"))


def test_practicals_only_is_a_rig_free_night_street_light():
    cat = Catalog.load()
    m = cat.get("lighting", "practicals_only")
    assert m is not None and m["directorSelectable"] is False          # new blocks land off the menu
    assert set(m["params"]) == {"exposure", "straySpill"}
    assert "practicals_only" in cat.get("world", "night_street")["lightingPairs"]
    src = (ROOT / "engine" / "blocks" / "lighting" / "practicals_only" / "build.py").read_text(encoding="utf-8")
    for rig in ("location_key import build", "area_light", "rim_neon_layout", "realise(", "black_card"):   # no rig
        assert rig not in src


def test_the_stray_spill_aims_past_the_cabin_away_from_the_lamp():
    from engine.blocks.lighting.practicals_only.build import stray_aim
    c, lamp = (0.0, 0.0, 1.0), (4.0, -2.0, 4.3)
    ax, ay, az = stray_aim(c, 1.8, lamp)
    assert az == c[2]
    d0 = math.hypot(lamp[0] - c[0], lamp[1] - c[1])
    assert math.hypot(lamp[0] - ax, lamp[1] - ay) > d0                  # beyond the centre, on the far side
    assert math.isclose(math.hypot(ax, ay), 0.35 * 1.8, rel_tol=1e-9)


def test_round13_night_script_uses_the_street_alone():
    sn = _load("street_night")
    assert sn["lighting"]["id"] == "practicals_only"
    assert sn["lighting"]["params"] == {"exposure": 0.4, "straySpill": 0.5}
    assert sn["grade"]["params"]["grain"] == 0.8                         # KEEP: grain, the darker noir grade
    assert sn["world"]["params"]["neonAmount"] == 0.0


def test_the_committed_night_reaches_the_render_as_asked():
    """The checker keeps practicals_only on the committed night script (r12's ask was swapped to neon rims)."""
    from harness import realism_round as rr
    from engine.checker import check
    import copy
    s = rr.load_script("street_night")
    r = check(copy.deepcopy(s), rr.load_profile(), Catalog.load())
    assert r.ok and r.script["lighting"] == s["lighting"]
    assert "lighting_world_mismatch" not in {i.code for i in r.issues}
