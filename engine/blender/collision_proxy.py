"""Collision shells built from the upload (phase 6 Task 97; METHODS R6/R8). Runs inside Blender.

Every sim collides with a proxy, never with the uploaded mesh: uploads are non-manifold, overlapping,
single-sided and far too dense for a solver. build_proxy() makes a closed shell from evaluated, world-space
COPIES of the subject's meshes (the upload's objects, meshes and materials are never modified):

1. join the copies into one temporary mesh;
2. Geometry Nodes `valora_proxy`: Mesh to SDF Grid (the purpose's voxel) -> SDF Grid Offset (+ one shell voxel,
   so a single-sided glass becomes a wall and every sim sees a solid) -> Grid to Mesh; if the 5.0 grid nodes are
   missing, a Solidify + voxel Remesh does the same job;
3. decimate (collapse) to the purpose's triangle cap; if that breaks watertightness, re-voxel coarser instead
   (the report records the effective voxel).

The result is applied to a new mesh datablock on a hidden object tagged valora_block = "proxy/<purpose>".
purpose "bullet_hull" returns <= 16 convex hulls (a greedy split along the longest axis until each part's hull
volume <= 1.3 x its voxel volume). write_ply / read_ply cache a proxy in the BakeStore (cached_proxy)."""
import math
import random
import struct

from engine.physics.proxy import HULL_FILL, max_hulls, max_tris, proxy_key, thickness_m, voxel_m

GROUP = "valora_proxy"
SDF_BAND = 3                 # voxels either side of the surface; >= 2 so a one-voxel offset stays in band
COVERAGE_Q = 0.95
WALL_Q = 0.02                # the 2nd-percentile wall (the thinnest real wall, not one crease sample)
WALL_RAYS = 1500
EPS = 1e-6


def _tag(ob, purpose):
    ob["valora_block"] = f"proxy/{purpose}"
    ob.hide_render = True
    ob.display_type = "WIRE"
    return ob


def _link(ob):
    import bpy
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _joined_copy(meshes):
    """One temporary mesh object holding evaluated, world-space copies of `meshes` (deformers applied)."""
    import bmesh
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            me.transform(o.matrix_world)
            bm.from_mesh(me)
        finally:
            ev.to_mesh_clear()
    data = bpy.data.meshes.new("valora_proxy_src")
    bm.to_mesh(data)
    bm.free()
    return _link(bpy.data.objects.new("valora_proxy_src", data))


def _grid_nodes_available():
    import bpy
    return all(hasattr(bpy.types, n) for n in ("GeometryNodeMeshToSDFGrid", "GeometryNodeSDFGridOffset",
                                               "GeometryNodeGridToMesh"))


def _sdf_group(voxel, offset):
    import bpy
    ng = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    sdf, off, g2m = n.new("GeometryNodeMeshToSDFGrid"), n.new("GeometryNodeSDFGridOffset"), n.new("GeometryNodeGridToMesh")
    sdf.inputs["Voxel Size"].default_value = voxel
    sdf.inputs["Band Width"].default_value = SDF_BAND
    off.inputs["Distance"].default_value = offset
    g2m.inputs["Threshold"].default_value = 0.0
    g2m.inputs["Adaptivity"].default_value = 0.0
    ln = ng.links
    ln.new(gi.outputs[0], sdf.inputs["Mesh"])
    ln.new(sdf.outputs[0], off.inputs["Grid"])
    ln.new(off.outputs[0], g2m.inputs["Grid"])
    ln.new(g2m.outputs[0], go.inputs[0])
    return ng


def _applied(src, name):
    """A new mesh datablock + object from src's evaluated modifiers; src is removed."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    data = bpy.data.meshes.new_from_object(src.evaluated_get(dg))
    data.name = name
    ob = _link(bpy.data.objects.new(name, data))
    for m in list(src.modifiers):
        grp = getattr(m, "node_group", None)
        src.modifiers.remove(m)
        if grp is not None and grp.users == 0:
            bpy.data.node_groups.remove(grp)
    bpy.data.objects.remove(src, do_unlink=True)
    return ob


def _voxel_shell(src, voxel, offset, method):
    """src (a joined copy) -> a closed shell object; src is consumed."""
    if method == "gn_sdf":
        mod = src.modifiers.new("valora_proxy", "NODES")
        mod.node_group = _sdf_group(voxel, offset)
    else:
        so = src.modifiers.new("valora_proxy_solidify", "SOLIDIFY")
        so.thickness, so.offset, so.use_rim, so.use_even_offset = 2 * offset, 0.0, True, True
        rm = src.modifiers.new("valora_proxy_remesh", "REMESH")
        rm.mode, rm.voxel_size, rm.adaptivity = "VOXEL", voxel, 0.0
    return _applied(src, "valora_proxy_shell")


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def watertight(ob):
    """Every edge has exactly two faces (a closed 2-manifold), and there is at least one face."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    ok = bool(bm.faces) and all(len(e.link_faces) == 2 for e in bm.edges)
    bm.free()
    return ok


def volume(ob):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = abs(bm.calc_volume(signed=True))
    bm.free()
    return v


def _decimated(ob, cap):
    import bpy
    t = tri_count(ob)
    if t <= cap:
        return ob, False
    mod = ob.modifiers.new("valora_proxy_decimate", "DECIMATE")
    mod.decimate_type, mod.ratio, mod.use_collapse_triangulate = "COLLAPSE", max(0.001, 0.97 * cap / t), True
    out = _applied(ob, "valora_proxy_shell")
    return out, True


def _bvh(ob):
    from mathutils.bvhtree import BVHTree
    import bpy
    return BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())


def coverage(ob, samples, q=COVERAGE_Q):
    """The q-quantile distance (metres) from the profile's surface samples to the proxy's solid: a sample inside
    the closed shell counts 0 (a car's seats and dashboard are surface samples, and the solid rightly swallows
    them), one outside counts its distance to the surface. So this measures where the shell falls short."""
    from mathutils import Vector
    if not samples:
        return 0.0
    tree = _bvh(ob)
    d = []
    for p in samples:
        v = Vector(p)
        loc, nrm, _, dist = tree.find_nearest(v)
        d.append(0.0 if loc is None or (v - loc).dot(nrm) < 0 else dist)
    d.sort()
    return d[min(len(d) - 1, int(q * (len(d) - 1) + 0.5))]


def excess(ob, meshes, q=COVERAGE_Q, n=2000, seed=0):
    """The q-quantile distance from the proxy's vertices to the upload's surface: how far the shell overshoots
    (one offset voxel plus about one voxel of meshing error when it hugs the model)."""
    import bpy
    from mathutils import Vector
    src = _joined_copy(meshes)
    try:
        tree = _bvh(src)
        vs = [v.co for v in ob.data.vertices]
        vs = vs if len(vs) <= n else random.Random(seed).sample(vs, n)
        d = sorted(tree.find_nearest(Vector(v))[3] for v in vs)
    finally:
        bpy.data.objects.remove(src, do_unlink=True)
    return d[min(len(d) - 1, int(q * (len(d) - 1) + 0.5))] if d else 0.0


def min_wall(ob, seed=0, rays=WALL_RAYS, q=WALL_Q):
    """The q-quantile wall thickness: from random face centres, the distance to the next surface along the
    inward normal."""
    from mathutils import Vector
    tree = _bvh(ob)
    polys = list(ob.data.polygons)
    rng = random.Random(seed)
    picks = polys if len(polys) <= rays else rng.sample(polys, rays)
    out = []
    for p in picks:
        n = -Vector(p.normal)
        o = Vector(p.center) + n * EPS * 10
        hit = tree.ray_cast(o, n)
        if hit[0] is not None:
            out.append(hit[3] + EPS * 10)
    out.sort()
    return out[min(len(out) - 1, int(q * (len(out) - 1) + 0.5))] if out else 0.0


def build_shell(meshes, profile, purpose, voxel=None):
    """(obj, report) for purpose shell / liquid / bullet."""
    import bpy
    voxel = float(voxel or voxel_m(profile, purpose))
    offset = thickness_m(profile)
    method = "gn_sdf" if _grid_nodes_available() else "remesh"
    cap = max_tris(purpose)
    ob = _voxel_shell(_joined_copy(meshes), voxel, offset, method)
    decimated = False
    if tri_count(ob) > cap:
        dec, decimated = _decimated(_link(ob.copy()), cap)      # linked, so the depsgraph evaluates it
        if watertight(dec):
            bpy.data.objects.remove(ob, do_unlink=True)
            ob = dec
        else:                                       # collapse broke the manifold: re-voxel coarser instead
            bpy.data.objects.remove(dec, do_unlink=True)
            t = tri_count(ob)
            bpy.data.objects.remove(ob, do_unlink=True)
            voxel = voxel * math.sqrt(t / cap) * 1.05
            ob = _voxel_shell(_joined_copy(meshes), voxel, offset, method)
            decimated = False
    ob.name = ob.data.name = f"valora_proxy_{purpose}"
    _tag(ob, purpose)
    samples = list(getattr(profile, "surfaceSamples", None) or [])
    report = {"purpose": purpose, "method": method, "voxelM": voxel, "thicknessM": offset, "tris": tri_count(ob),
              "maxTris": cap, "decimated": decimated, "watertight": watertight(ob),
              "coverage95M": coverage(ob, samples), "excess95M": excess(ob, meshes), "minWallM": min_wall(ob),
              "volumeM3": volume(ob)}
    return ob, report


def _principal_split(pts):
    """Split points at the median of their longest bounding-box extent."""
    ext = [(max(p[i] for p in pts) - min(p[i] for p in pts), i) for i in range(3)]
    ax = max(ext)[1]
    vals = sorted(p[ax] for p in pts)
    cut = vals[len(vals) // 2]
    return ax, cut


def _inside_points(shell, step):
    """Voxel centres inside the closed shell (nearest-face normal test)."""
    from mathutils import Vector
    tree = _bvh(shell)
    lo = [min(v.co[i] for v in shell.data.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in shell.data.vertices) for i in range(3)]
    n = [max(1, int(math.ceil((hi[i] - lo[i]) / step))) for i in range(3)]
    out = []
    for ix in range(n[0]):
        for iy in range(n[1]):
            for iz in range(n[2]):
                p = Vector((lo[0] + (ix + 0.5) * step, lo[1] + (iy + 0.5) * step, lo[2] + (iz + 0.5) * step))
                loc, nrm, _, _ = tree.find_nearest(p)
                if loc is not None and (p - loc).dot(nrm) < 0:
                    out.append(tuple(p))
    return out


def _hull_object(pts, name, purpose):
    import bmesh
    import bpy
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts)
    kill = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    data = bpy.data.meshes.new(name)
    bm.to_mesh(data)
    bm.free()
    return _tag(_link(bpy.data.objects.new(name, data)), purpose)


def build_hulls(meshes, profile, max_parts=None):
    """(hull objects, report) for an active Bullet subject: <= max_hulls() convex hulls."""
    import bpy
    max_parts = max_parts or max_hulls()
    shell, rep = build_shell(meshes, profile, "bullet")
    step = rep["voxelM"]
    inside = _inside_points(shell, step)
    verts = [tuple(v.co) for v in shell.data.vertices]
    cell = step ** 3

    def measure(part):
        """(fill ratio, wasted m^3): the part's hull volume over its voxel volume, and their difference."""
        ins, vs = part
        if len(vs) < 4 or not ins:
            return 1.0, 0.0
        ob = _hull_object(vs, "valora_tmp_hull", "bullet_hull")
        hv, iv = volume(ob), cell * len(ins)
        bpy.data.objects.remove(ob, do_unlink=True)
        return hv / max(iv, 1e-12), hv - iv

    parts = [(inside, verts)]
    stats = [measure(parts[0])]
    final = set()                       # parts too small to split further
    while len(parts) < max_parts:
        # split the part wasting the most volume (a tiny sliver with a bad ratio wastes little)
        open_ = [j for j in range(len(parts)) if j not in final and stats[j][0] > HULL_FILL]
        if not open_:
            break
        k = max(open_, key=lambda j: stats[j][1])
        ins, vs = parts[k]
        ax, cut = _principal_split(ins) if len(ins) >= 8 else (0, None)
        a = ([p for p in ins if p[ax] < cut], [p for p in vs if p[ax] < cut + step]) if cut is not None else ([], [])
        b = ([p for p in ins if p[ax] >= cut], [p for p in vs if p[ax] >= cut - step]) if cut is not None else ([], [])
        if not a[0] or not b[0]:
            final.add(k)
            continue
        parts[k:k + 1] = [a, b]
        stats[k:k + 1] = [measure(a), measure(b)]
        final = {j + 1 if j > k else j for j in final}
    ratios = [s[0] for s in stats]
    hulls = [_hull_object(vs, f"valora_proxy_hull_{i:02d}", "bullet_hull")
             for i, (ins, vs) in enumerate(parts) if len(vs) >= 4]
    bpy.data.objects.remove(shell, do_unlink=True)
    report = {"purpose": "bullet_hull", "voxelM": step, "hulls": len(hulls),
              "fill": [round(r, 4) for r in ratios], "shellVolumeM3": rep["volumeM3"],
              "hullVolumeM3": sum(volume(h) for h in hulls), "watertight": all(watertight(h) for h in hulls)}
    return hulls, report


def build_proxy(meshes, profile, purpose, voxel=None):
    """(obj, report) for shell / liquid / bullet; (list of hull objects, report) for bullet_hull."""
    if purpose == "bullet_hull":
        return build_hulls(meshes, profile)
    return build_shell(meshes, profile, purpose, voxel)


# --- the cache: a proxy as a binary little-endian PLY (triangles), stdlib only ------------------------------

def write_ply(ob, path):
    me = ob.data
    me.calc_loop_triangles()
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    with open(path, "wb") as f:
        f.write(("ply\nformat binary_little_endian 1.0\ncomment valora collision proxy\n"
                 f"element vertex {len(me.vertices)}\nproperty float x\nproperty float y\nproperty float z\n"
                 f"element face {len(tris)}\nproperty list uchar int vertex_indices\nend_header\n").encode("ascii"))
        for v in me.vertices:
            f.write(struct.pack("<3f", *v.co))
        for t in tris:
            f.write(struct.pack("<B3i", 3, *t))


def read_ply(path, name, purpose):
    import bpy
    with open(path, "rb") as f:
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
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    return _tag(_link(bpy.data.objects.new(name, data)), purpose)


def cached_proxy(meshes, profile, purpose, store, model_sha):
    """build_proxy through the BakeStore (key engine.physics.proxy.proxy_key): a hit reads proxy.ply and its
    report; a miss builds, writes and commits. bullet_hull is not cached (it is cheap next to its bake)."""
    if purpose == "bullet_hull":
        return build_proxy(meshes, profile, purpose)
    voxel = voxel_m(profile, purpose)
    key = proxy_key(model_sha, purpose, voxel)
    hit = store.read(key)
    if hit is not None:
        ob = read_ply(store.path(key) / "proxy.ply", f"valora_proxy_{purpose}", purpose)
        return ob, {**hit["proxy"], "fromCache": True}
    ob, report = build_proxy(meshes, profile, purpose)
    with store.writer(key) as w:
        write_ply(ob, w.dir / "proxy.ply")
        w.report({"proxy": report})
    return ob, {**report, "fromCache": False}
