"""The Mantaflow gas bake helper (phase 6 Task 111; reused by smoke_sim T113 and ink_cloud T117).

The measured 5.0.1 recipe (engine/bake/formats.py gas_vdb, the T94 probe): a GAS domain with cache_type 'ALL',
cache_data_format 'OPENVDB' and cache_directory set, baked with bpy.ops.fluid.bake_all() under
temp_override(object=domain, active_object=domain, scene); the sequence is <dir>/data/fluid_data_####.vdb with
the grids density, flame, shadow, temperature and velocity. Half-float VDB with Blosc compression keeps the cache
small; noise upres is off (preview tier, see engine/physics/gas.py). Obstacles are closed shells (T97) as
COLLISION effectors; a proxy parented to the subject's rig is a moving obstacle (Mantaflow reads its animation).

After a bake, keep_vdb_only() deletes Mantaflow's config / non-VDB files so a BakeStore cache holds only the
sequence. density_stats() samples the domain's density_grid per frame (the evaluated cache) for the probes:
the density sum, NaN, and the voxels above EPS inside an obstacle (at that frame's obstacle pose)."""
import os
import shutil
import time
from pathlib import Path

import bpy

PARK_Z = -1.0e4           # a flow parked here emits into no domain
EPS = 0.02               # (eng) a voxel denser than this counts as smoke for the inside probe


def _enum_ok(owner, prop, value):
    return value in [i.identifier for i in owner.bl_rna.properties[prop].enum_items]


def domain(name, lo, hi, *, res, frame_start, frame_end, cache_dir, vorticity=0.1, dissolve=None,
           time_scale=1.0, flame_vorticity=None, burning_rate=None):
    """A GAS domain box from lo to hi (placed metres), resolution_max res, baking frame_start..frame_end into
    cache_dir as OpenVDB (half float, Blosc). dissolve: frames for smoke to fade (None: no dissolve)."""
    me = bpy.data.meshes.new(name)
    v = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    fm = ob.modifiers.new("Fluid", "FLUID")
    fm.fluid_type = "DOMAIN"
    ds = fm.domain_settings
    ds.domain_type = "GAS"
    ds.resolution_max = int(res)
    ds.cache_type = "ALL"
    ds.cache_data_format = "OPENVDB"
    if _enum_ok(ds, "openvdb_data_depth", "16"):
        ds.openvdb_data_depth = "16"
    if _enum_ok(ds, "openvdb_cache_compress_type", "BLOSC"):
        ds.openvdb_cache_compress_type = "BLOSC"
    ds.cache_directory = str(cache_dir)
    ds.cache_frame_start, ds.cache_frame_end = int(frame_start), int(frame_end)
    ds.vorticity = float(vorticity)
    ds.use_noise = False
    ds.time_scale = float(time_scale)
    if dissolve:
        ds.use_dissolve_smoke = True
        ds.dissolve_speed = int(dissolve)
    ds.use_adaptive_domain = False
    if flame_vorticity is not None:
        ds.flame_vorticity = float(flame_vorticity)
    if burning_rate is not None:
        ds.burning_rate = float(burning_rate)
    ob.hide_render = True
    return ob


def source(name, centre, radius, *, kind="SMOKE", temperature=1.0, density=1.0, fuel=1.0, velocity=None,
           frames=None, colour=(0.7, 0.7, 0.7), mesh_ob=None, depth=None, volume_density=None,
           surface_distance=None):
    """A flow emitting from a flat disc (or mesh_ob): smoke / fire / both, with an initial velocity; frames
    (first, last): it emits only then, parked far outside every domain before and after (CONSTANT location
    keys; None: it emits over the whole bake)."""
    if mesh_ob is None:
        me = bpy.data.meshes.new(name)
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=radius, radius2=radius,
                              depth=depth or max(0.02, 0.15 * radius))
        bm.to_mesh(me)
        bm.free()
        mesh_ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(mesh_ob)
        mesh_ob.location = centre
    fm = mesh_ob.modifiers.new("Fluid", "FLUID")
    fm.fluid_type = "FLOW"
    fs = fm.flow_settings
    fs.flow_type = kind
    fs.flow_behavior = "INFLOW"
    fs.flow_source = "MESH"
    fs.surface_distance = surface_distance if surface_distance is not None else max(0.01, 0.5 * radius)
    if volume_density is not None:
        fs.volume_density = float(volume_density)          # emit from the whole mesh, not only its skin
    fs.temperature = float(temperature)
    fs.density = float(density)
    fs.smoke_color = colour[:3]
    if kind in ("FIRE", "BOTH"):
        fs.fuel_amount = float(fuel)
    if velocity is not None and any(velocity):
        fs.use_initial_velocity = True
        fs.velocity_coord = velocity
    if frames:                        # 5.0.1 flows have no use_flow: park the emitter outside the domain instead
        a, b = frames
        home, away = tuple(mesh_ob.location), (mesh_ob.location[0], mesh_ob.location[1], PARK_Z)
        for fr, loc in ((a - 1, away), (a, home), (b, home), (b + 1, away)):
            mesh_ob.location = loc
            mesh_ob.keyframe_insert("location", frame=fr)
        from engine.blender.realism_rig import fcurves
        for c in fcurves(mesh_ob.animation_data.action):
            for kp in c.keyframe_points:
                kp.interpolation = "CONSTANT"
        mesh_ob.location = home
    mesh_ob.hide_render = True
    return mesh_ob


def obstacle(ob):
    """A closed shell as a COLLISION effector (moving when its parent is animated)."""
    fm = ob.modifiers.new("Fluid", "FLUID")
    fm.fluid_type = "EFFECTOR"
    es = fm.effector_settings
    es.effector_type = "COLLISION"
    es.use_effector = True
    if hasattr(es, "subframes"):
        es.subframes = 1
    ob.hide_render = True
    return ob


def bake(dom, scene=None):
    """bpy.ops.fluid.bake_all under the measured override; returns (seconds, [vdb paths in order])."""
    scene = scene or bpy.context.scene
    ds = dom.modifiers["Fluid"].domain_settings
    t = time.perf_counter()
    with bpy.context.temp_override(object=dom, active_object=dom, scene=scene):
        r = bpy.ops.fluid.bake_all()
    secs = time.perf_counter() - t
    if "FINISHED" not in r:
        raise RuntimeError(f"fluid.bake_all returned {r}")
    return secs, vdb_files(ds.cache_directory)


def vdb_files(cache_dir):
    d = Path(cache_dir) / "data"
    return sorted(d.glob("fluid_data_*.vdb")) if d.is_dir() else []


def keep_vdb_only(cache_dir):
    """Delete everything Mantaflow wrote except data/*.vdb (config/*.uni, noise, guides): a cache holds only the
    sequence the build reads."""
    root = Path(cache_dir)
    for p in list(root.iterdir()):
        if p.name == "data" and p.is_dir():
            for f in p.iterdir():
                if f.suffix != ".vdb":
                    f.unlink()
        elif p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.parent == root and p.suffix != ".json":
            try:
                p.unlink()
            except OSError:
                pass


def cache_bytes(cache_dir):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(cache_dir) for f in fs)


def density_stats(dom, frames, obstacles=(), eps=EPS, stride=2):
    """Per sampled frame: the density sum, whether every value is finite, and the smoke voxels (> eps) inside
    each obstacle at that frame's pose (a moving shell is tested where it is then), from the domain's
    evaluated density_grid (x fastest). stride samples every stride-th voxel on each axis."""
    import math
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    scene = bpy.context.scene
    ds = dom.modifiers["Fluid"].domain_settings
    trees = []
    for ob in obstacles:
        me = ob.data
        trees.append((ob, BVHTree.FromPolygons([v.co[:] for v in me.vertices], [p.vertices[:] for p in me.polygons])))
    out = []
    for f in frames:
        scene.frame_set(int(f))
        dg = bpy.context.evaluated_depsgraph_get()
        ev = dom.evaluated_get(dg)
        eds = ev.modifiers["Fluid"].domain_settings
        rx, ry, rz = eds.domain_resolution[:]
        dens = eds.density_grid[:]
        if len(dens) != rx * ry * rz:
            out.append({"frame": int(f), "sum": 0.0, "finite": True, "smoke": 0, "inside": 0, "res": [rx, ry, rz]})
            continue
        corners = [dom.matrix_world @ Vector(c) for c in dom.bound_box]
        lo = [min(c[i] for c in corners) for i in range(3)]
        hi = [max(c[i] for c in corners) for i in range(3)]
        sz = [(hi[i] - lo[i]) / r for i, r in enumerate((rx, ry, rz))]
        total, finite, smoke, inside = 0.0, True, 0, 0
        inv = [(ob.matrix_world.inverted(), tr) for ob, tr in trees]
        for k in range(0, rz, stride):
            for j in range(0, ry, stride):
                base = (k * ry + j) * rx
                for i in range(0, rx, stride):
                    d = dens[base + i]
                    if not math.isfinite(d):
                        finite = False
                        continue
                    total += d
                    if d <= eps:
                        continue
                    smoke += 1
                    if inv:
                        p = Vector((lo[0] + (i + 0.5) * sz[0], lo[1] + (j + 0.5) * sz[1], lo[2] + (k + 0.5) * sz[2]))
                        for mi, tr in inv:
                            q = mi @ p
                            loc, nrm, _, _ = tr.find_nearest(q)
                            if loc is not None and (q - loc).dot(nrm) < 0:
                                inside += 1
                                break
        out.append({"frame": int(f), "sum": round(total * stride ** 3, 4), "finite": finite, "smoke": smoke,
                    "inside": inside, "res": [rx, ry, rz]})
    return out
