"""Review chunk5 #6: on a plinth (plinth_spin, standsOn plinth) the contact deformers clamp against the plinth
top, not the world floor. soft_rest and tyre_contact lowered the subject (dip, tyre deflection) and clamped at
world z = 0, which is under the plinth: the subject sank into it by the whole drop."""
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.physics import applies, contact
from engine.tests.conftest import requires_blender
from engine.tests.test_realism_blender import _script

FIX = Path(__file__).parent / "fixtures"


def _plinth(s):
    s["subject"]["motion"] = {"id": "plinth_spin", "params": {"turnDeg": 90.0, "turnS": 6.0, "startS": 1.0}}
    return s


def test_the_contact_plane_is_the_plinth_top_only_on_a_plinth():
    from engine.profile import SubjectProfile
    cat = Catalog.load()
    prof = SubjectProfile.from_dict(json.loads((FIX / "profiles" / "sneaker.json").read_text(encoding="utf-8")))
    h = cat.motion_module("plinth_spin").plinth_height(prof)
    assert applies.contact_plane_m(_plinth(_script()), prof, cat) == pytest.approx(h) and h > 0
    assert applies.contact_plane_m(_script(), prof, cat) == 0.0
    grass = {**_plinth(_script()), "world": {"id": "golden_field", "params": {}}}
    assert cat.get("world", "golden_field")["groundType"] == "grass"
    assert applies.contact_world(grass, cat)["groundType"] == "studio"         # a hard top, whatever the world


@pytest.mark.blender
@requires_blender
def test_a_soft_subject_on_a_plinth_rests_on_its_top(tmp_path):
    from engine.compiler.run import compile_scene
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("plush", tmp_path / "plush.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    h = Catalog.load().motion_module("plinth_spin").plinth_height(prof)
    res = compile_scene(_plinth(_script()), prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",),
                        realism_probe=[1])
    assert "soft_rest" in res["realism"]
    dip = res["realismScene"]["soft_dip_m"]
    assert dip > 0.002                                   # it does dip (hard top: capped at HARD_DIP_MAX_M)
    rec = res["realismProbe"]["1"]
    assert rec["minZ"] >= h - contact.GROUND_TOL_M, (rec["minZ"], h, dip)          # not pressed into the plinth
    assert rec["minZ"] <= h + contact.GROUND_TOL_M                                # and not floating above it
    assert rec["footprintM"] > 0.02                      # the clamp made a flat footprint on the top


@pytest.mark.blender
@requires_blender
def test_tyres_on_a_plinth_flatten_on_its_top(tmp_path):
    from engine.compiler.run import compile_scene
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    from engine.tests.realism_catalog import catalog_with_fixtures
    glb = make_glb("wheeled", tmp_path / "wheeled.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    # the 4 m fixture is past plinth_spin's 2.5 m size cap (a 1-2.5 m wheeled subject is not): widen it in a copy
    cat = catalog_with_fixtures(tmp_path / "cat")
    bj = Path(cat.root) / "motion" / "plinth_spin" / "block.json"
    bj.write_text(json.dumps({**json.loads(bj.read_text(encoding="utf-8")), "subjectSizeM": [0.02, 5.0]}), encoding="utf-8")
    cat = Catalog.load(cat.root)
    h = cat.motion_module("plinth_spin").plinth_height(prof)
    res = compile_scene(_plinth(_script()), prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",),
                        realism_probe=[1], catalog=cat)
    assert "tyre_contact" in res["realism"] and res["realismScene"]["tyre_d_m"] > 0.005
    rec = res["realismProbe"]["1"]
    for i, w in enumerate(prof.wheels):
        t = rec["tyres"][str(i)]
        assert t["minZ"] >= h - contact.GROUND_TOL_M, (i, t, h)
        assert t["flatLenM"] >= 0.5 * 0.45 * w["radius"], (i, t)       # a real patch, pressed on the top
