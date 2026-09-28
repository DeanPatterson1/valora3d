"""shatter bake (phase 6 Task 102, stage 4b only; METHODS M-FRAC, DS-01). Breaks a PROP, never the subject.

- The prop (engine.physics.fracture box coordinates: width X, thickness Y, height Z) is cut into seeded Voronoi
  cells, dense near the impact point; each cell is built from its vertices (the Cell Fracture extension is not
  bundled) as its own ACTIVE CONVEX_HULL shard, origin at its centroid, SHRINK smaller, use_margin + margin 0,
  held kinematic (keyed) until one frame before the hit, so the prop stands whole until something hits it.
- impact burst: the prop stands on the ground behind the subject (on the side away from the hero camera,
  facing it); a hidden kinematic sphere flies through it from behind at IMPACT_S into the window on one straight
  rising path that passes over the subject. impact subject_through: the prop stands across the moving subject's
  path (slide_in, drop_settle), where the subject's leading face has covered THROUGH of its travel; the subject
  collides as its convex hulls (bullet_hull), keyed from the rig. A static subject falls back to burst (reported
  as impactUsed). The closed shell is used only by simProbe (no shard inside the subject).
- Bullet as in rigid_scatter (60 substeps, 20 iterations, no force fields); frame_set, keys.json rows. The shard
  meshes (pane-local, around each centroid) and the target go to keys.json "info" so build() rebuilds them."""
import json
import math
from pathlib import Path

# The bake key hashes this file and build.py only (engine/bake/run.block_sha), not engine/blender/pieces.py:
# bump MESH_REV whenever a piece mesh or the Bullet helpers there change, or a stale cache is reused.
MESH_REV = 11

IMPACT_S = 0.3             # (eng) seconds into the window when the burst hits
SHRINK = 0.02             # (eng) shard gap: 2% of each shard about its centroid (the crack width reads as a crack)
IMPACT_MS = 2.5            # (eng) projectile speed in sim m/s for a 0.5 m prop (x sqrt(width / 0.5))
IMPACT_RISE = 0.6          # (eng) the projectile climbs 0.6 per unit of travel: over the subject, away from the pile
THROUGH = 0.6              # (eng) share of the subject's travel at which its leading face meets the prop
TARGETS = {                # (eng) width x longest, height rule, thickness x width (clamped), friction, restitution
    "prop_glass": {"thick": (0.012, 0.003, 0.012), "friction": 0.5, "restitution": 0.1, "density": 2500},
    "prop_ice": {"thick": (0.15, 0.01, 0.6), "friction": 0.1, "restitution": 0.1, "density": 917},
    "prop_wall": {"thick": (0.08, 0.01, 0.4), "friction": 0.8, "restitution": 0.05, "density": 1800},
}


def pane_dims(target, profile):
    """(width, thickness, height): wide enough to frame the subject, and taller than it so a burst above its top
    reads (clip r1: a 1.4 x longest pane ran out of a 9:16 frame and its burst hid behind the shoe)."""
    w = 1.1 * profile.longest
    h = max(1.6 * profile.sizeM[2], 0.6 * w)
    k, lo, hi = TARGETS[target]["thick"]
    return w, min(hi, max(lo, k * w)), h


def _frame(d, up=(0.0, 0.0, 1.0)):
    """Pane axes: local Y along d (the pane's normal), X horizontal across it, Z completing a right-handed frame."""
    from mathutils import Vector
    y = Vector(d).normalized()
    x = y.cross(Vector(up))
    if x.length < 1e-6:
        x = Vector((1.0, 0.0, 0.0))
    x.normalize()
    z = x.cross(y).normalized()
    return x, y, z


def _matrix(origin, axes):
    from mathutils import Matrix
    x, y, z = axes
    return Matrix(((x[0], y[0], z[0], origin[0]), (x[1], y[1], z[1], origin[1]), (x[2], y[2], z[2], origin[2]),
                   (0, 0, 0, 1)))


def _subject_path(sc, fr, profile):
    """The subject's centre and its rig matrix at every bake frame."""
    from mathutils import Vector
    from engine.blender.realism_rig import rig
    off = rig()[1]
    c = Vector(profile.center)
    out, mats = [], []
    for f in range(fr["bake_first"], fr["bake_last"] + 1):
        sc.frame_set(f)
        out.append(off.matrix_world @ c)
        mats.append(off.matrix_world.copy())
    sc.frame_set(fr["bake_first"])   # back to the start: Bullet builds its world from the poses at the current frame
    return out, mats


def _keyed_collider(sc, shell, mats, fr):
    """An UNPARENTED copy of the shell keyed LINEAR with the rig's world matrix at every bake frame: measured
    2026-09-28, a kinematic MESH body parented to the moving rig did not follow it in Bullet (the prop exploded
    on frame 1 against the shell's rest pose), so the collider carries its own keys."""
    import bpy
    from engine.blender.realism_rig import fcurves
    src = shell[0] if isinstance(shell, list) else shell
    ob = bpy.data.objects.new(f"valora_shatter_collider_{src.name}", src.data)
    sc.collection.objects.link(ob)
    ob.rotation_mode = "QUATERNION"
    base = src.matrix_parent_inverse.copy() if src.parent is not None else None
    for f, m in zip(range(fr["bake_first"], fr["bake_last"] + 1), mats):
        w = m @ base if base is not None else m
        ob.matrix_world = w
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_quaternion", frame=f)
        ob.keyframe_insert("scale", frame=f)
    for c in fcurves(ob.animation_data.action):
        for kp in c.keyframe_points:
            kp.interpolation = "LINEAR"
    sc.frame_set(fr["bake_first"])
    return ob


def bake(ctx):
    import bmesh
    import bpy
    from mathutils import Vector
    from engine.blender import pieces as P
    from engine.motion_path import is_moving
    from engine.physics import fracture as F
    p, prof, b, sc = ctx.params, ctx.profile, ctx.bake, ctx.scene
    fr = b["frames"]
    fps = sc.render.fps / sc.render.fps_base
    w, t, h = pane_dims(p["target"], prof)
    impact = p["impact"]
    moving = is_moving(ctx.script, prof, ctx.catalog)
    path, mats = _subject_path(sc, fr, prof) if impact == "subject_through" and moving else (None, None)
    if path is not None and (path[-1] - path[0]).length < 1e-4:
        path = None
    used = "subject_through" if path is not None else "burst"
    shell = b["proxy"]["shell"]
    c = Vector(prof.center)
    if used == "burst":
        cam = Vector(ctx.hero_pose.position)
        away = Vector((c.x - cam.x, c.y - cam.y, 0.0))
        away = away.normalized() if away.length > 1e-6 else Vector((0.0, 1.0, 0.0))
        foot = math.hypot(prof.half[0], prof.half[1])
        origin = Vector((c.x, c.y, 0.0)) + away * (foot * 1.15 + 0.3 * w + t / 2) + Vector((0, 0, h / 2))
        axes = _frame(-away)                         # the pane faces the camera; its normal points at the subject
        # the hit lands above the subject's top (pane-local z from the pane's centre), so the burst is seen
        top = prof.boundsMax[2] - h / 2
        ix, iz = ctx.rng.uniform(-0.12, 0.12) * w, min(0.4 * h, max(top + 0.12 * h, 0.1 * h))
        hit_f = fr["bake_first"] + int(round(IMPACT_S * fps))
    else:
        d = path[-1] - path[0]
        travel = d.length
        d.normalize()
        lead = max((Vector(corner) - c).dot(d) for corner in
                   [(x, y, z) for x in (prof.boundsMin[0], prof.boundsMax[0]) for y in (prof.boundsMin[1], prof.boundsMax[1])
                    for z in (prof.boundsMin[2], prof.boundsMax[2])])
        s = path[0].dot(d) + lead + THROUGH * travel
        # where the leading face meets the plane: the first frame whose centre passes s - lead
        k = next((i for i, q in enumerate(path) if q.dot(d) >= s - lead), len(path) - 1)
        hit = path[k]
        origin = hit + d * (lead + t / 2)
        if abs(d.z) < 0.7:                           # a standing prop: on the ground
            origin.z = h / 2
        axes = _frame(d)
        ix, iz = 0.0, 0.0
        hit_f = fr["bake_first"] + k
    M = _matrix(origin, axes)
    box = (w, t, h)
    sites = F.sites(box, int(p["cells"]), (ix, iz), ctx.seed)
    cells = F.cells(box, sites)
    P.rigid_world(sc, fr, p["timeScale"])
    P.ground_slab(prof)
    if used == "subject_through":
        # the moving subject collides as its convex hulls (bullet_hull), never the hollow MESH shell: shards caught
        # inside a moving triangle soup were squeezed through the floor or thrown 1.5 m (measured 2026-09-28)
        hulls = b["proxy"]["bullet_hull"]
        hulls = hulls if isinstance(hulls, list) else [hulls]
        P.passive([_keyed_collider(sc, h_, mats, fr) for h_ in hulls], "CONVEX_HULL", friction=0.5,
                  restitution=0.1, animated=True)
    else:
        P.passive(shell, "MESH", friction=0.5, restitution=0.1)
    obs, info = [], {}
    for i, cell in enumerate(cells):
        ctr = F.centroid(cell)
        # every shard shrunk by SHRINK about its centroid: coincident neighbour faces at margin 0 overlap numerically,
        # and releasing 40 overlapping bodies at once blew shards 0.8 m high off a 0.2 m pane (measured 2026-09-28)
        local = [[(v[k] - ctr[k]) * (1 - SHRINK) for k in range(3)] for v in cell["verts"]]
        name = f"valora_shard_{i:03d}"
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in local]
        for f in cell["faces"]:
            try:
                bm.faces.new([vs[j] for j in f])
            except ValueError:
                pass
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        sc.collection.objects.link(ob)
        ob.matrix_world = M @ _matrix(ctr, (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))))
        ob.rotation_mode = "QUATERNION"
        obs.append(ob)
        # build() renders the UNSHRUNK cell (no visible gaps): the shrink is a collision-only clearance
        info[name] = {"verts": [[round(x / (1 - SHRINK), 6) for x in v] for v in local], "faces": cell["faces"]}
    bpy.context.view_layer.update()
    vols = [abs(F.volume(cl)) for cl in cells]
    P.active(obs, "gems", [v ** (1 / 3) for v in vols])
    tg = TARGETS[p["target"]]
    # The prop is held whole by keying every shard KINEMATIC ("Animated") until just before the hit, then dynamic.
    # use_start_deactivated did not hold it (measured 2026-09-28: the coincident faces of neighbouring cells woke
    # them, and a pane across a slide_in path fell apart on frame 1).
    release = max(fr["bake_first"] + 1, hit_f - 1)
    for ob, v in zip(obs, vols):
        rb = ob.rigid_body
        rb.friction, rb.restitution = tg["friction"], tg["restitution"]
        rb.mass = max(1e-5, tg["density"] * v)
        rb.kinematic = True
        ob.keyframe_insert("rigid_body.kinematic", frame=fr["bake_first"])
        ob.keyframe_insert("rigid_body.kinematic", frame=release - 1)
        rb.kinematic = False
        ob.keyframe_insert("rigid_body.kinematic", frame=release)
    if used == "burst":
        # The hidden projectile: a straight LINEAR path through the impact point, rising IMPACT_RISE per unit of
        # travel, at IMPACT_MS (sim m/s, scaled with the prop). It never stops or jumps (a kinematic jump is an
        # infinite speed that flings whatever it touches: clip r1 lost a shard 3 m through the floor that way),
        # and it passes over the subject.
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=max(0.02 * w, 1.5 * t))
        imp = bpy.context.object
        n = (Vector(axes[1]) + Vector((0.0, 0.0, IMPACT_RISE))).normalized()     # towards the subject, rising
        at = M @ Vector((ix, 0.0, iz))
        step = IMPACT_MS * math.sqrt(w / 0.5) * float(p["timeScale"]) / fps     # metres per frame
        f0, f1 = fr["bake_first"] - 1, fr["bake_last"] + 1
        for f in (f0, f1):
            imp.location = at + n * step * (f - hit_f)
            imp.keyframe_insert("location", frame=f)
        from engine.blender.realism_rig import fcurves
        for c in fcurves(imp.animation_data.action):
            for kp in c.keyframe_points:
                kp.interpolation = "LINEAR"
        P.passive(imp, "SPHERE", friction=0.2, restitution=0.2, animated=True)
    rows = P.record(sc, obs, fr)
    Path(b["dir"], "keys.json").write_text(json.dumps(
        {"frames": [fr["bake_first"], fr["bake_last"]], "pieces": rows,
         "info": {"target": p["target"], "shards": info, "impactUsed": used, "impactFrame": hit_f,
                  "release": release, "pane": {"dims": [w, t, h], "matrix": [list(r) for r in M]}}},
        separators=(",", ":")), encoding="utf-8")
    moved = sum(1 for r in rows.values() if math.dist(r[0][:3], r[-1][:3]) > 0.25 * t + 1e-4)
    return {"shards": len(obs), "moved": moved, "impactUsed": used, "impactFrame": hit_f,
            "paneOrigin": [round(v, 4) for v in origin],
            "subjectPath": [[round(v, 4) for v in q] for q in (path[0], path[len(path) // 2], path[-1])] if path else None,
            "pane": [round(w, 4), round(t, 4), round(h, 4)]}
