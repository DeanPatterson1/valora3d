"""Review chunk5 #8, #9: the weather Geometry Nodes, measured on evaluated geometry (compile only, never render).

#8: rain crowns are scaled by their OWN age after the lifetime and shelter deletions compact the point indices.
#9: the recorded `velocity` of rain drops and snow flakes is the time derivative of their evaluated positions
    (mean drift + the gust displacement's derivative), checked against a central finite difference."""
import math
import subprocess
from pathlib import Path

import pytest

from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]
ROOT = Path(__file__).resolve().parents[2]

_SETUP = r'''
import sys
sys.path.insert(0, r"{root}")
import bpy, numpy as np
from types import SimpleNamespace as NS
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
cam.location = (8.0, -6.0, 1.6)
scene.camera = cam
off = bpy.data.objects.new("valora_realism_offset", None)
scene.collection.objects.link(off)
prof = NS(center=(0.0, 0.0, 0.25), boundsMin=(-0.5, -0.5, 0.0), boundsMax=(0.5, 0.5, 0.5), longest=1.0, radius=0.7,
          sizeM=(1.0, 1.0, 0.5))
'''

_CROWNS = _SETUP + r'''
from engine.blender import weather_nodes as wn
from engine.blender.gn import Tree, add_modifier
from engine.physics import rain as R
lat = R.impact_lattice(50.0, 2.0, 12.0, 3)
DROP_R, TUBE = 0.004, 0.12
imp = wn.weather_object(scene, "imp", "test")
g = Tree("imp")
scale = wn.lattice_impacts(g, lat, wn.box_centre(g, (0.0, 0.0)), DROP_R)
wn.shelter(g, off, (-1.5, -1.5, 0.0), (1.5, 1.5, 1.0), top=False)   # a big footprint: many cells deleted
wn.instance(g, wn.ring(g, TUBE), scale)
add_modifier(imp, g.finish(), "imp")
print("LAT", lat["across"] ** 2)
for f in (10, 25, 40):
    scene.frame_set(f)
    ev = imp.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    red = np.empty(n, np.float32); me.attributes["valora_red"].data.foreach_get("value", red)
    age = np.empty(n, np.float32); me.attributes["valora_age"].data.foreach_get("value", age)
    ev.to_mesh_clear()
    keys = np.round(red, 6)
    for k in np.unique(keys):
        sel = keys == k
        if sel.sum() != 24 * 6:             # one ring = 24 x 6 vertices; skip any red shared by two cells
            continue
        c = co[sel]
        print("CROWN", f, float(age[sel][0]), float(np.ptp(c[:, 0]) / 2.0), float(np.ptp(c[:, 2])))
'''


def _blender(script_text, tmp_path, name):
    from engine.ingest.run import BLENDER
    script = tmp_path / name
    script.write_text(script_text, encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    return [ln.split() for ln in proc.stdout.splitlines()]


def test_crown_size_follows_its_own_age_after_deletions(tmp_path):                  # review chunk5 #8
    rows = _blender(_CROWNS.format(root=ROOT), tmp_path, "crowns.py")
    total = next(int(r[1]) for r in rows if r[:1] == ["LAT"])
    crowns = [[float(v) for v in r[1:]] for r in rows if r[:1] == ["CROWN"]]
    for f in (10.0, 25.0, 40.0):                                     # deletions happened, crowns survive
        alive = sum(1 for c in crowns if c[0] == f)
        assert 10 <= alive < total, (f, alive, total)
    drop_r, tube = 0.004, 0.12
    for f, age, half_xy, z in crowns:
        spread = drop_r * (2.0 + 10.0 * age)                         # lattice_impacts' crown law
        tall = drop_r * 0.8 * max(1.0 - age, 0.0)
        assert 0.0 <= age <= 1.0
        # the ring: radius 1 + tube in xy (both polygons have a vertex on their +x axis); the hexagonal profile is
        # 2 x tube x sin(60 deg) tall; each scaled by the crown's own spread / tall
        assert half_xy == pytest.approx(spread * (1.0 + tube), rel=1e-3), (f, age, half_xy, spread)
        assert z == pytest.approx(2.0 * tube * math.sin(math.radians(60.0)) * tall, rel=1e-3, abs=1e-7), (f, age, z, tall)


_VELOCITY = _SETUP + r'''
from engine.blender.weather_nodes import SHELTER
from engine.blender.wind_field import ensure_wind_group
from engine.physics import wind as W
wp = {{"directionDeg": 30.0, "speedMs": 6.0, "gustiness": 1.0, "turbulence": 1.0}}
scene["valora_wind"] = wp
ensure_wind_group(wp, 5)
ctx = NS(scene=scene, profile=prof, catalog=None, seed=11, camera_positions=[(8.0, -6.0, 1.6)], camera_lenses_mm=[50.0],
         script={{"format": {{"fps": 24}}, "effects": [{{"id": "{effect}"}}], "seed": 1}}, hero_pose=None)
if "{effect}" == "rain":
    from engine.blocks.effect.rain.build import build
    ctx.params = {{"intensity": "drizzle", "rateMmH": 0.0, "dropSizeMm": 0.0, "impacts": False, "backlight": 0.0}}
    ob = build(ctx)
else:
    from engine.blocks.effect.snow import build as S
    ctx.params = {{"rate": 0.4, "flakeMm": 6.0, "accumulationMm": 0.0, "onSubject": False}}
    wind = W.vector(30.0, 6.0 * 0.9)
    ob = S._flakes(bpy, ctx, S._snow_material(bpy), wind[:2], 0.9)[0]
ob.modifiers[0].node_group.nodes[SHELTER].mute = True    # keep every point: indices match across frames
ob.modifiers[1].show_viewport = False                     # the points themselves, not the instanced drops


def read(f, sub):
    scene.frame_set(f, subframe=sub)
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get("co", co)
    v = np.empty(n * 3, np.float32); me.attributes["velocity"].data.foreach_get("vector", v)
    ev.to_mesh_clear()
    return co.reshape(-1, 3), v.reshape(-1, 3).astype(np.float64)


H = 0.1                                                    # frames either side of frame 20
a, _ = read(19, 1.0 - H)
b, _ = read(20, H)
_, vel = read(20, 0.0)
dt = 2.0 * H / scene.render.fps
fd = (b - a) / dt
keep = np.linalg.norm(b - a, axis=1) < 0.5                 # drop the points that wrapped at a box face
err = np.linalg.norm(fd[keep] - vel[keep], axis=1)
gust = np.linalg.norm(fd[keep, :2] - np.median(fd[keep, :2], axis=0), axis=1)
print("VEL", int(keep.sum()), len(keep), float(err.max()), float(np.median(err)), float(np.percentile(gust, 90)))
'''


@pytest.mark.parametrize("effect", ["rain", "snow"])
def test_recorded_velocity_is_the_derivative_of_the_evaluated_position(effect, tmp_path):   # review chunk5 #9
    """dt = 0.2 frame at 24 fps (8.3 ms, central difference); tolerance 0.05 m/s absolute: the central-difference
    truncation plus float32 positions (~4e-6 m at 40 m / 8.3 ms ~ 1e-3 m/s) sit well under it, while recording the
    local wind instead (the defect) is off by |wind - mean|, metres per second at gustiness 1."""
    rows = _blender(_VELOCITY.format(root=ROOT, effect=effect), tmp_path, f"vel_{effect}.py")
    kept, n, err_max, err_med, gust90 = next([float(v) for v in r[1:]] for r in rows if r[:1] == ["VEL"])
    assert kept > 0.9 * n and n > 100, (kept, n)
    assert gust90 > 0.05, gust90                       # the gusts really move the points (the check is not vacuous)
    assert err_max < 0.05, (err_max, err_med)
