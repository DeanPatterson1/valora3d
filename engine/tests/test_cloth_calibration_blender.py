"""Task 107: the wind force-field calibration with a cloth strip (the phase-5 deferral of FF_STRENGTH_PER_MS).

A 1 m x 0.5 m silk strip (engine/physics/cloth presets at REF_SPACING) hangs pinned along its top edge in the one
WIND field (engine/blender/wind_field.ensure_force_field, flow 0, no gusts). Its trailing (bottom) edge's mean
deflection from the vertical over 2-3 s is measured over a ladder of field strengths; for each speed (2, 5, 10
m/s) the strength that gives the quasi-static drag angle (tan theta = F_drag / W, C_d 1.2, real silk weight) is
interpolated, and FF_STRENGTH_PER_MS2 is their fit (strength = K v^2, because Blender's WIND pushes a face by
strength x area, like a pressure, and drag pressure goes with v^2). A final run at the committed constant checks
the angles and the wind_coherent probe. Everything is recorded in var/probe/cloth_calibration.json.

Serial: runs under the machine bake lock. About 1-2 min."""
import json
import math
import subprocess
from pathlib import Path

import pytest

from engine.bake.lock import machine_lock
from engine.blender_cli import blender_argv
from engine.physics import cloth as C
from engine.physics import wind_calibration as W
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "var" / "probe" / "cloth_calibration.json"
SPEEDS = (2.0, 5.0, 10.0)
LADDER = (1e3, 3e3, 1e4, 3e4, 1e5, 3e5, 1e6)

_STRIP = r'''
import bpy, json, math, sys
A = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, A[0])
from engine.blender import cloth as BC
from engine.blender.wind_field import ensure_force_field
from engine.physics import cloth as C
from engine.physics.wind_calibration import coherent
preset, runs, fps, secs = A[1], json.loads(A[2]), 24, 3.0
out = []
for run in runs:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    nf = int(secs * fps)
    sc.frame_start, sc.frame_end = 1, nf
    nx, ny, sp = C.grid_dims(0.5, 1.0, C.REF_SPACING)
    verts, faces = BC.grid_mesh(nx, ny, sp)
    verts = [(x, 0.0, 1.0 + y) for x, y, _ in verts]            # stand it up: top row at z = 1.5
    ob = BC.sheet("strip", verts, faces, pins=[(ny - 1) * nx + i for i in range(nx)])
    BC.apply_cloth(ob, preset, sp, longest=1.0, frame_range=(1, nf))
    BC.wind_response(ob, preset)
    f = ensure_force_field({"speedMs": run.get("speedMs", 1.0), "gustiness": 0.0, "directionDeg": 90.0}, 7)
    if "strength" in run:
        f.field.strength = run["strength"]
    f.field.flow = 0.0
    ang, first, last = [], None, None
    for fr in range(1, nf + 1):
        sc.frame_set(fr)
        ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        b = [ev.data.vertices[i].co.copy() for i in range(nx)]
        c = [sum(v[k] for v in b) / nx for k in range(3)]
        if fr == 1:
            first = c
        if fr >= 2 * fps:
            ang.append(math.degrees(math.atan2(c[1], 1.5 - c[2])))
        last = c
    finite = all(a == a and abs(a) != float("inf") for a in ang)
    mean = sum(ang) / len(ang) if ang and finite else None
    out.append({**run, "strengthSet": f.field.strength, "meanDeg": mean, "minDeg": min(ang) if finite else None,
                "maxDeg": max(ang) if finite else None, "finite": finite,
                "coherent": coherent([last[0] - first[0], last[1] - first[1], 0.0], 90.0, run.get("speedMs", 0.0))})
print("PROBE_JSON " + json.dumps(out), flush=True)
'''


def _run(tmp_path, preset, runs):
    script = tmp_path / "strip.py"
    script.write_text(_STRIP, encoding="utf-8")
    with machine_lock(timeout_s=3600):
        proc = subprocess.run(blender_argv(script, [ROOT, preset, json.dumps(runs)]), capture_output=True,
                              text=True, timeout=1800)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON ")]
    assert proc.returncode == 0 and lines, f"blender failed ({proc.returncode}):\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
    return json.loads(lines[-1][len("PROBE_JSON "):])


def _interp_strength(ladder, target_deg):
    """log-strength interpolation of the measured (strength, angle) ladder at target_deg (angles must rise)."""
    pts = sorted((r["strength"], r["meanDeg"]) for r in ladder if r["finite"])
    for (s0, a0), (s1, a1) in zip(pts, pts[1:]):
        if a0 <= target_deg <= a1 and a1 > a0:
            t = (target_deg - a0) / (a1 - a0)
            return math.exp(math.log(s0) + t * (math.log(s1) - math.log(s0)))
    return None


def test_wind_strength_calibrated_on_a_silk_strip(tmp_path):
    ladder = _run(tmp_path, "silk", [{"strength": s} for s in LADDER])
    angles = [r["meanDeg"] for r in ladder]
    assert all(r["finite"] for r in ladder), ladder
    assert angles == sorted(angles), f"deflection must rise with strength: {angles}"
    areal = C.PRESETS["silk"]["arealKgM2"]
    fit = {}
    for v in SPEEDS:
        s = _interp_strength(ladder, C.drag_angle_deg(v, areal))
        fit[v] = None if s is None else s / (v * v)
    ks = [k for k in fit.values() if k]
    assert ks, f"no speed's model angle falls inside the ladder: {angles}"
    k_fit = math.exp(sum(map(math.log, ks)) / len(ks))
    check = _run(tmp_path, "silk", [{"speedMs": v} for v in (0.0, 1.0) + SPEEDS])
    rec = {"preset": "silk", "strip": "1.0 x 0.5 m, pinned top edge, REF_SPACING %.3f" % C.REF_SPACING,
           "model": "tan(theta) = 0.5 rho C_d v^2 / (areal g); C_d %.2f, areal %.3f kg/m2" % (C.CD_FLAG, areal),
           "ladder": ladder, "fitPerMs2": {str(k): v for k, v in fit.items()}, "kFit": k_fit,
           "committed": W.FF_STRENGTH_PER_MS2, "before": {"FF_STRENGTH_PER_MS": 0.8, "law": "linear"},
           "check": [{**r, "modelDeg": C.drag_angle_deg(r["speedMs"], areal) if r["speedMs"] else 0.0} for r in check]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    # the committed constant is the fit (within 15%: a re-run on another box moves the flutter average slightly)
    assert abs(math.log(W.FF_STRENGTH_PER_MS2 / k_fit)) < math.log(1.15), rec["fitPerMs2"]
    by = {r["speedMs"]: r for r in check}
    assert by[0.0]["meanDeg"] == 0.0                                       # calm: hangs straight
    for v in SPEEDS:
        assert abs(by[v]["meanDeg"] - C.drag_angle_deg(v, areal)) <= 10.0, (v, by[v])
        assert by[v]["coherent"]["ok"] is True, by[v]                      # wind_coherent at >= 1.5 m/s
