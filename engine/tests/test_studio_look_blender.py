"""The studio_cyc + reflection_rig look in Blender: a black cyc must read as a dark floor (the rig
lights the subject, never the set) and no set edge or rig object may reach the camera."""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from engine.compiler.run import compile_scene
from engine.ingest.run import BLENDER
from engine.profile import SubjectProfile
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]
FIX = Path(__file__).parent / "fixtures"
MODEL = Path(__file__).resolve().parents[2] / "assets-in" / "models" / "toycar" / "toycar.glb"
T3_PROBE = [1, 60, 61, 105, 106, 165, 166, 210, 211, 256, 300]  # both ends of every shot
RIG = ("valora_overhead", "valora_strip_", "valora_accent_", "valora_rim")

_INSPECT = r'''
import bpy, json, sys
from mathutils import Vector
out, frames = sys.argv[-2], [int(f) for f in sys.argv[-1].split(",")]
sc = bpy.context.scene
res = {"links": {}, "rays": {}}
for o in sc.objects:
    if o.type != "LIGHT":
        continue
    rc = o.light_linking.receiver_collection
    res["links"][o.name] = None if rc is None else [
        [ob.name, co.light_linking.link_state] for ob, co in zip(rc.objects, rc.collection_objects)]
cyc = sc.objects["valora_cyc"]
inv = cyc.matrix_world.inverted()
xs = [v.co.x for v in cyc.data.vertices]; ys = [v.co.y for v in cyc.data.vertices]
zs = [v.co.z for v in cyc.data.vertices]
cam = sc.camera
for f in frames:
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    tr, br, bl, tl = [cam.matrix_world @ v for v in cam.data.view_frame(scene=sc)]
    org = cam.matrix_world.translation
    bad = []
    nx, ny = 12, 20
    for i in range(nx):
        for j in range(ny):
            a, b = i / (nx - 1), j / (ny - 1)
            d = (bl.lerp(br, a).lerp(tl.lerp(tr, a), b) - org).normalized()
            o, what = org.copy(), "escape"
            for _ in range(64):
                hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, d)
                if not hit:
                    break
                ob = ob.original
                if ob.visible_camera and ob.name != "valora_haze":
                    what = ob.name
                    if ob is cyc:
                        p = inv @ loc
                        m = 0.02
                        edge = (p.x < min(xs) + m * (max(xs) - min(xs)) or p.x > max(xs) - m * (max(xs) - min(xs))
                                or p.y < min(ys) + m * (max(ys) - min(ys)) or p.z > max(zs) - m * (max(zs) - min(zs)))
                        what = "cyc_edge" if edge else "cyc"
                    break
                o = loc + d * 1e-6
            if what in ("escape", "cyc_edge") or (what != "cyc" and what.startswith("valora")):
                bad.append(what)
    res["rays"][str(f)] = {"n": nx * ny, "bad": bad}
open(out, "w").write(json.dumps(res))
'''


def _profile():
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / "toycar.json").read_text(encoding="utf-8")))


def _script():
    return json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def t3_scene(tmp_path_factory):
    if not MODEL.exists():
        pytest.skip("model not present")
    tmp = tmp_path_factory.mktemp("t3scene")
    compile_scene(_script(), _profile(), MODEL, tmp, render=False, save_blend=True)
    script, out = tmp / "inspect.py", tmp / "inspect.json"
    script.write_text(_INSPECT, encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--disable-autoexec",
                           str(tmp / "scene.blend"), "--python", str(script), "--python-exit-code", "1",
                           "--", str(out), ",".join(map(str, T3_PROBE))],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0 and out.exists(), proc.stderr[-2000:]
    return json.loads(out.read_text(encoding="utf-8"))


def test_rig_lights_never_light_the_set(t3_scene):
    links = t3_scene["links"]
    rig = [n for n in links if n.startswith(RIG)]
    assert rig
    for n in rig:
        assert links[n], n
        assert ["valora_cyc", "EXCLUDE"] in links[n] and all(s == "EXCLUDE" for _, s in links[n]), n


def test_the_floor_pool_lights_only_the_set(t3_scene):
    links = t3_scene["links"]
    assert links.get("valora_floor_pool") == [["valora_cyc", "INCLUDE"]]


def test_no_set_edge_or_rig_object_reaches_the_camera(t3_scene):
    for f in T3_PROBE:
        rec = t3_scene["rays"][str(f)]
        assert rec["n"] >= 200 and rec["bad"] == [], (f, sorted(set(rec["bad"])))


def test_black_cyc_is_a_dark_floor_and_the_subject_stays_lit(tmp_path):
    """script_t3 hero frame, haze off. Before the fix the black floor rendered ~109/255 (the rig's
    overhead and rim lit it and it mirrored them); a black studio floor must read dark."""
    from PIL import Image
    compile_scene(_script(), _profile(), MODEL, tmp_path, tier="keyframes", frames=[256], skip_kinds=("effect",))
    rgb = np.asarray(Image.open(tmp_path / "beauty" / "0256.png").convert("RGB"), dtype=np.float32).mean(axis=2)
    mask = np.asarray(Image.open(next((tmp_path / "passes").glob("mask*0256*.png"))).convert("L")) > 127
    h = rgb.shape[0]
    floor = np.zeros_like(mask)
    floor[int(0.6 * h):] = True
    floor &= ~mask
    assert floor.sum() > 0.2 * rgb.size and mask.any()
    assert rgb[floor].mean() <= 30, rgb[floor].mean()
    assert np.percentile(rgb[floor], 99) >= 2 * np.median(rgb[floor]) + 4  # a pool, not a flat black
    assert rgb[mask].mean() >= 100, rgb[mask].mean()
