"""The cloth base (phase 6 Task 107): Blender legacy cloth set from engine/physics/cloth presets, stepped with
frame_set and written to PC2 (formats.FORMATS['cloth_pc2']); the compile reads it back with a MESH_CACHE modifier
(sample i plays at modifier.frame_start + i; the PC2 header's start frame is ignored). Colliders are the subject's
closed shell (the bake's proxy) and a ground plane at z = 0, never the upload.

bake side: sheet(), apply_cloth(), collider(), ground_collider(), bake_pc2().
build side: cached_sheet() - the sheet mesh from mesh.json plus a MESH_CACHE modifier; no CLOTH modifier ever
reaches a compile (SimInCompile)."""
import json
import math
from pathlib import Path

from engine.bake.formats import pc2_frame_bytes, pc2_header
from engine.physics import cloth as C

PC2 = "cloth.pc2"
MESH = "mesh.json"


def grid_mesh(nx, ny, spacing, name="valora_cloth"):
    """(verts, faces): an nx x ny grid in the XY plane centred on the origin, row-major (index = j * nx + i)."""
    w, h = (nx - 1) * spacing, (ny - 1) * spacing
    verts = [(-w / 2 + i * spacing, -h / 2 + j * spacing, 0.0) for j in range(ny) for i in range(nx)]
    faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
             for j in range(ny - 1) for i in range(nx - 1)]
    return verts, faces


def sheet(name, verts, faces, pins=(), collection=None):
    """A mesh object at the world origin (identity transform, so PC2 local == world) with a 'pin' group."""
    import bpy
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    g = ob.vertex_groups.new(name="pin")
    if pins:
        g.add(list(pins), 1.0, "REPLACE")
    return ob


def apply_cloth(ob, preset, spacing, *, longest, time_scale=1.0, self_collision=False, quality=None,
                pin_stiffness=1.0, frame_range=None):
    """The CLOTH modifier with the scaled preset. Returns the settings actually set (read back from Blender,
    because RNA clamps silently)."""
    s = C.settings(preset, spacing)
    md = ob.modifiers.new("valora_cloth", "CLOTH")
    cs, cc = md.settings, md.collision_settings
    cs.mass = s["mass"]
    cs.tension_stiffness = s["tension"]
    cs.compression_stiffness = s["compression"]
    cs.shear_stiffness = s["shear"]
    cs.bending_stiffness = s["bending"]
    cs.tension_damping = s["damping"]
    cs.compression_damping = s["damping"]
    cs.shear_damping = s["damping"]
    cs.air_damping = s["air"]
    cs.time_scale = float(time_scale)
    n = len(ob.data.vertices)
    cs.quality = int(quality or C.quality(n, self_collision))
    cs.vertex_group_mass = "pin"
    cs.pin_stiffness = pin_stiffness
    cc.use_collision = True
    cc.distance_min = C.distance_min(longest)
    cc.collision_quality = 3
    cc.use_self_collision = bool(self_collision)
    if self_collision:
        cc.self_distance_min = C.distance_min(longest) * 0.5
    if frame_range is not None:
        md.point_cache.frame_start, md.point_cache.frame_end = int(frame_range[0]), int(frame_range[1])
    return {"mass": cs.mass, "tension": cs.tension_stiffness, "bending": cs.bending_stiffness,
            "air": cs.air_damping, "quality": cs.quality, "distanceMin": cc.distance_min,
            "selfCollision": cc.use_self_collision, "timeScale": cs.time_scale, "scale": s["scale"]}


def wind_response(ob, preset):
    """Set the cloth's wind effector weight (engine/physics/cloth.wind_weight); gravity stays 1."""
    md = next(m for m in ob.modifiers if m.type == "CLOTH")
    md.settings.effector_weights.wind = C.wind_weight(preset)
    return md.settings.effector_weights.wind


def collider(ob, longest, friction=5.0):
    """Make an existing proxy a cloth collider (COLLISION modifier; thickness from the cloth distance rule)."""
    if not any(m.type == "COLLISION" for m in ob.modifiers):
        ob.modifiers.new("valora_collision", "COLLISION")
    c = ob.collision
    c.thickness_outer = C.distance_min(longest)
    c.thickness_inner = min(0.2, max(0.001, 0.02 * float(longest)))
    c.cloth_friction = float(friction)
    c.use_culling = False
    return ob


def ground_collider(size, name="valora_cloth_ground"):
    """A hidden plane at z = 0 the cloth lands on (the world's own ground is left alone)."""
    import bpy
    h = size / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.hide_render = True
    ob.modifiers.new("valora_collision", "COLLISION")
    ob.collision.thickness_outer = 0.001
    ob.collision.cloth_friction = 1.0          # (eng) fabric drags on the floor but slides
    return ob


def edges(faces):
    """Unique undirected quad edges (structural springs) of a face list."""
    seen = set()
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            seen.add((min(a, b), max(a, b)))
    return sorted(seen)


def bake_pc2(scene, ob, first, last, out_dir, faces, on_frame=None, scale=1.0):
    """Step the cloth with frame_set from `first` to `last` (inclusive), write every evaluated vertex set to
    out_dir/cloth.pc2 (object-local == world: the sheet has an identity transform) and the rest mesh to
    mesh.json. Returns stats: samples, verts, bytes, maxStretch (worst structural edge vs rest, any frame),
    finite, maxSpeedMs. `scale` multiplies every written position (a sheet simulated enlarged is written back at
    real size)."""
    import bpy
    out = Path(out_dir)
    rest = [tuple(c * scale for c in v.co) for v in ob.data.vertices]
    es = edges([tuple(f) for f in faces])
    rest_len = [math.dist(rest[a], rest[b]) for a, b in es]
    n, samples = len(rest), last - first + 1
    fps = scene.render.fps / scene.render.fps_base
    worst, finite, vmax, prev = 1.0, True, 0.0, None
    with open(out / PC2, "wb") as fh:
        fh.write(pc2_header(n, float(first), 1.0, samples))
        for f in range(first, last + 1):
            scene.frame_set(f)
            if on_frame is not None:
                on_frame(f)
            ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
            co = [tuple(c * scale for c in v.co) for v in ev.data.vertices]
            if len(co) != n:
                raise RuntimeError(f"cloth vertex count changed at frame {f}: {len(co)} != {n}")
            if not all(math.isfinite(c) for p in co for c in p):
                finite = False
            else:
                for (a, b), r in zip(es, rest_len):
                    if r > 0:
                        worst = max(worst, math.dist(co[a], co[b]) / r)
                if prev is not None:
                    vmax = max(vmax, max(math.dist(p, q) for p, q in zip(co, prev)) * fps)
            prev = co
            fh.write(pc2_frame_bytes(co))
    (out / MESH).write_text(json.dumps({"verts": [[round(c, 6) for c in v] for v in rest], "faces": faces,
                                        "first": first, "last": last}), encoding="utf-8")
    return {"samples": samples, "verts": n, "bytes": (out / PC2).stat().st_size, "maxStretch": round(worst, 4),
            "finite": finite, "maxSpeedMs": round(vmax, 4)}


def cached_sheet(ctx, name, block_id):
    """build(): the baked sheet as a mesh with a MESH_CACHE modifier playing cloth.pc2, sample i at render frame
    bake_first + offset + i. Raises BakeMissing when the cache is absent."""
    import bpy
    from engine.bake.run import BakeMissing
    b = ctx.bake
    d = Path(b["dir"]) if b else None
    if d is None or not (d / PC2).is_file() or not (d / MESH).is_file():
        raise BakeMissing(f"{block_id}: no {PC2} / {MESH} in {b and b.get('dir')}")
    m = json.loads((d / MESH).read_text(encoding="utf-8"))
    ob = sheet(name, m["verts"], m["faces"])
    ob["valora_block"] = f"sim/{block_id}"
    mc = ob.modifiers.new("valora_cloth_cache", "MESH_CACHE")
    mc.cache_format = "PC2"
    mc.filepath = str(d / PC2)
    mc.frame_start = float(m["first"] + b["frames"]["offset"])
    if hasattr(ob, "cycles") and hasattr(ob.cycles, "use_deform_motion"):
        ob.cycles.use_deform_motion = True          # R7: the cache deforms, Cycles blurs it
    return ob, m


def read_pc2(path):
    """(header, [[(x, y, z)] per sample]) of a PC2 file (probe and tests)."""
    import struct
    data = Path(path).read_bytes()
    sig, ver, n, start, rate, samples = struct.unpack("<12siiffi", data[:32])
    frames, off = [], 32
    for _ in range(samples):
        vals = struct.unpack(f"<{3 * n}f", data[off:off + 12 * n])
        frames.append([tuple(vals[i:i + 3]) for i in range(0, 3 * n, 3)])
        off += 12 * n
    return {"verts": n, "start": start, "rate": rate, "samples": samples}, frames

