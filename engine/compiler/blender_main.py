"""Runs INSIDE Blender. Builds the scene for an already-checked script and renders the requested
frames. Launch only through engine/compiler/run.py, which runs the checker first."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))  # phase-1 carry-forward: the engine package is importable here

import bpy  # noqa: E402

from engine.blender.scene_io import import_subject, world_bounds  # noqa: E402
from engine.profile import SubjectProfile  # noqa: E402

PLACEMENT_TOL = 1e-4  # of the subject's longest side


def place_subject(objs, profile):
    """placed = (v - (sourceCenter.xy, sourceMinZ)) * scaleFactor, as a root empty's transform."""
    root = bpy.data.objects.new("valora_subject", None)
    bpy.context.scene.collection.objects.link(root)
    for o in objs:
        if o.parent is None:
            o.parent = root  # parent inverse stays identity, so the root transform applies as-is
    f, c = profile.scaleFactor, profile.sourceCenter
    root.scale = (f, f, f)
    root.location = (-c[0] * f, -c[1] * f, -profile.sourceMinZ * f)
    bpy.context.view_layer.update()
    return root


def assert_placement(meshes, profile):
    lo, hi = world_bounds(meshes, bpy.context.evaluated_depsgraph_get())
    got = [float(v) for v in list(lo) + list(hi)]
    want = list(profile.boundsMin) + list(profile.boundsMax)
    tol = PLACEMENT_TOL * max(profile.sizeM) + 1e-6
    if profile.boundsPosed:  # this pose must fit inside the union over all poses
        ok = all(g >= w - tol for g, w in zip(got[:3], want[:3])) and all(g <= w + tol for g, w in zip(got[3:], want[3:]))
    else:
        ok = all(abs(g - w) <= tol for g, w in zip(got, want))
    if not ok:
        raise SystemExit(f"placement mismatch: got {got}, profile says {want}")
    return got


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    out = Path(job["out"])
    profile = SubjectProfile.from_dict(job["profile"])
    objs, meshes = import_subject(job["model"])
    root = place_subject(objs, profile)
    result = {"blender": bpy.app.version_string, "placedBounds": assert_placement(meshes, profile)}
    # Tasks 20-24: build_all(...), camera, passes, render.
    if job.get("saveBlend"):
        bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"))
    (out / "compile.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
