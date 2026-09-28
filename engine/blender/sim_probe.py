"""compile.json.simProbe (phase 6 Task 99): the sim hygiene probes, REPORT-ONLY until calibrated. Runs inside
Blender after every block is built. Per baked sim:

- no_particles_in_subject: piece centres (rigid_keys: every baked frame from keys.json) or evaluated points of
  the sim's objects (other methods: at the probe frames) inside the subject's closed shell, read back from the
  proxy cache the bake used (its key is in the bake manifest). Inside = the nearest shell face's normal points
  away from the point (the same test collision_proxy.coverage uses);
- sim_stable: engine/physics/sim_stats (NaN / inf, speed cap, rigid kinetic-energy decay);
- velocity_present: keyed pieces carry object motion (object motion blur); point geometry a 'velocity'
  attribute; a Volume its velocity_grid; a mesh sequence cache its 'velocity' attribute;
- bake_cost: the manifest's bakeSeconds and cache bytes.
The shell is the rest-pose shell: a moving subject's sims are judged against the rest pose (report-only, noted
for the lanes that key a moving collider)."""
import json
from pathlib import Path

from engine.physics import sim_stats

DEFAULT_MAX_SPEED = 10.0     # (eng) m/s when a manifest gives no bake.maxSpeedMs


def _proxy_tree(bake):
    """A BVH of the shell the bake collided with, or None."""
    from mathutils.bvhtree import BVHTree
    key = (((bake.get("manifest") or {}).get("proxy") or {}).get("shell") or {}).get("key")
    if not key:
        return None
    root = Path(bake["dir"]).parent
    ply = root / key / "proxy.ply"
    if not ply.is_file():
        return None
    import struct
    with open(ply, "rb") as f:
        head = []
        while True:
            line = f.readline().decode("ascii").strip()
            head.append(line)
            if line == "end_header":
                break
        nv = int(next(h.split()[2] for h in head if h.startswith("element vertex")))
        nf = int(next(h.split()[2] for h in head if h.startswith("element face")))
        verts = [struct.unpack("<3f", f.read(12)) for _ in range(nv)]
        faces = [struct.unpack("<B3i", f.read(13))[1:] for _ in range(nf)]
    return BVHTree.FromPolygons(verts, faces)


def _inside(tree, p):
    from mathutils import Vector
    v = Vector(p)
    loc, nrm, _, _ = tree.find_nearest(v)
    return loc is not None and (v - loc).dot(nrm) < 0


def _objects(scene, sid):
    return [o for o in scene.objects if o.get("valora_block") == f"sim/{sid}"]


def _velocity_present(scene, obs, method):
    if not obs:
        return False
    if method == "rigid_keys":
        return all(o.animation_data is not None and o.animation_data.action is not None for o in obs)
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    for o in obs:
        if o.type == "VOLUME":
            if not getattr(o.data, "velocity_grid", ""):
                return False
            continue
        ev = o.evaluated_get(dg)
        data = getattr(ev, "data", None)
        attrs = getattr(data, "attributes", None)
        if attrs is None or "velocity" not in attrs:
            return False
    return True


def _points(scene, obs, frame, cap=5000):
    import bpy
    scene.frame_set(int(frame))
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in obs:
        ev = o.evaluated_get(dg)
        data = getattr(ev, "data", None)
        attrs = getattr(data, "attributes", None)
        pos = attrs.get("position") if attrs is not None else None
        if pos is None or len(pos.data) > cap:
            out.append(tuple(o.matrix_world.translation))
            continue
        mw = o.matrix_world
        out.extend(tuple(mw @ d.vector) for d in pos.data)
    return out


def sim_probe(scene, profile, frames, bakes, catalog):
    keep = scene.frame_current
    out = {}
    for sid, b in (bakes or {}).items():
        m = catalog.get("sim", sid) or {}
        method = b.get("method") or (m.get("bake") or {}).get("method")
        vmax = float((m.get("bake") or {}).get("maxSpeedMs", DEFAULT_MAX_SPEED))
        man = b.get("manifest") or {}
        if not man:
            from engine.bake.store import BakeStore
            man = BakeStore(Path(b["dir"]).parent).read(b["key"], verify="none") or {}
            b = {**b, "manifest": man}
        tree = _proxy_tree(b)
        fps = scene.render.fps / scene.render.fps_base
        rec = {"method": method, "reportOnly": True, "bakeSeconds": man.get("bakeSeconds"),
               "cacheBytes": sum(f["bytes"] for f in (man.get("files") or {}).values())}
        obs = _objects(scene, sid)
        if method == "rigid_keys":
            keys = json.loads((Path(b["dir"]) / "keys.json").read_text(encoding="utf-8"))
            pieces = list(keys["pieces"].values())
            n = min(len(rows) for rows in pieces) if pieces else 0
            series = [[tuple(rows[f][:3]) for rows in pieces] for f in range(n)]
            rec["stable"] = sim_stats.rigid_verdict(series, fps, vmax)
            flags = [_inside(tree, p) for fr in series for p in fr] if tree is not None else []
        else:
            pts = [p for f in (frames or []) for p in _points(scene, obs, f)]
            rec["stable"] = {"finite": all(all(c == c and abs(c) != float("inf") for c in p) for p in pts),
                             "ok": None}
            flags = [_inside(tree, p) for p in pts] if tree is not None else []
        rec["inside"] = sim_stats.inside_verdict(flags) if tree is not None else {"ok": None, "why": "no shell"}
        rec["velocityPresent"] = _velocity_present(scene, obs, method)
        out[sid] = rec
    scene.frame_set(keep)
    return out
