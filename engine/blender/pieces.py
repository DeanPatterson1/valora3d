"""Procedural rigid pieces for the rigid lane (phase 6 Tasks 100-102): CC0 by construction, real size, built the
same way in the bake (collision hulls) and in the compile (render meshes), so a baked transform always drives the
mesh that was simulated. Also the fast rigid_keys keyer (foreach_set on F-curves: 500 pieces x 240 frames is
~840k keys, far too many for keyframe_insert).

Mesh size: the piece's LONGEST dimension equals piece_size_m (engine/physics/scatter.PIECE_SIZE_M); the seeded
0.85-1.15 jitter is the object's scale. Shapes (METHODS M-RB pieces): a bean is a squashed, bent UV sphere (kidney);
a coffee bean an ellipsoid with a centre groove on its flat face; ice a rounded cube; a gem a round brilliant
(crown, girdle, pavilion); a coin a bevelled cylinder; a pill a capsule; a candy a lentil; a pebble a
noise-dented icosphere. Materials are Principled presets looked up by node type."""
import math
import random

VARIANTS = {"beans": 3, "coffee_beans": 3, "pebbles": 4, "ice": 2, "candies": 1, "gems": 1, "coins": 1,
            "pills": 1, "shards": 4, "leaves_dry": 3}
# (base colour, roughness, metallic, transmission, subsurface weight, coat) (eng presets; G1 owner grade)
PRESETS = {
    "beans": ((0.30, 0.055, 0.035), 0.35, 0.0, 0.0, 0.15, 0.3),
    "coffee_beans": ((0.065, 0.03, 0.013), 0.42, 0.0, 0.0, 0.05, 0.15),   # dark roast (clip r1: read as milk chocolate)
    "ice": ((0.92, 0.96, 1.0), 0.06, 0.0, 1.0, 0.0, 0.0),
    "gems": ((0.85, 0.9, 1.0), 0.0, 0.0, 1.0, 0.0, 0.0),
    "coins": ((0.95, 0.72, 0.38), 0.22, 1.0, 0.0, 0.0, 0.0),
    "pills": ((0.93, 0.92, 0.9), 0.45, 0.0, 0.0, 0.3, 0.0),
    "candies": ((0.75, 0.08, 0.06), 0.15, 0.0, 0.0, 0.2, 0.8),
    "pebbles": ((0.17, 0.16, 0.145), 0.85, 0.0, 0.0, 0.0, 0.0),   # clip r1: 0.36 blew out to white eggs
    "shards": ((0.03, 0.03, 0.035), 0.08, 0.0, 0.0, 0.0, 0.0),      # obsidian-dark, glossy fracture faces
    "leaves_dry": ((0.36, 0.19, 0.07), 0.65, 0.0, 0.0, 0.25, 0.0),
}
FRICTION = {"coins": 0.5, "ice": 0.15}          # (eng) default 0.6
RESTITUTION = {"coins": 0.3, "gems": 0.3}       # (eng) default 0.2
DENSITY = {"beans": 1200, "coffee_beans": 650, "ice": 917, "gems": 3500, "coins": 8500, "pills": 1300,
           "candies": 1400, "pebbles": 2600}     # kg/m^3


def _bm_to_mesh(bpy, bm, name):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _fit(bm, size):
    """Scale the bmesh so its longest dimension is `size`, centred on its bounds centre."""
    xs = [[v.co[i] for v in bm.verts] for i in range(3)]
    c = [(max(a) + min(a)) / 2 for a in xs]
    ext = max(max(a) - min(a) for a in xs)
    k = size / ext
    for v in bm.verts:
        v.co = [(v.co[i] - c[i]) * k for i in range(3)]


# Mesh resolution per level of detail. Bullet's convex-hull support search is linear in the hull's points, and a
# 222-vertex bean made a 500-piece pile bake for > 28 min (killed 2026-09-28); the bake collides with the coarse
# "collide" mesh, scaled up by COLLIDE_PAD[kind] so its hull contains the render mesh (pieces rest a fraction of a
# millimetre proud rather than sinking in), and the compile renders the fine one.
RES = {"render": {"u": 20, "v": 12, "ico": 3, "bevel": 3, "coin": 40},
       "collide": {"u": 10, "v": 7, "ico": 1, "bevel": 1, "coin": 12}}
COLLIDE_PAD = {"beans": 1 / math.cos(math.pi / 10), "coffee_beans": 1 / math.cos(math.pi / 10),
               "candies": 1 / math.cos(math.pi / 10), "pills": 1 / math.cos(math.pi / 10),
               "coins": 1 / math.cos(math.pi / 12), "pebbles": 1.08, "ice": 1.04, "gems": 1.0}


def piece_mesh(kind, size, variant=0, lod="render"):
    """A real-size mesh for one piece kind and variant (seeded by the variant, so bake and build agree)."""
    import bmesh
    import bpy
    r = RES[lod]
    name = f"valora_piece_{kind}_{variant}" + ("" if lod == "render" else f"_{lod}")
    me = bpy.data.meshes.get(name)
    if me is not None:
        return me
    rng = random.Random(1000 + 17 * variant + sum(map(ord, kind)))
    bm = bmesh.new()
    if kind in ("beans", "coffee_beans", "candies"):
        bmesh.ops.create_uvsphere(bm, u_segments=r["u"], v_segments=r["v"], radius=0.5)
        sx, sy, sz = {"beans": (1.0, 0.6, 0.45), "coffee_beans": (1.0, 0.75, 0.52),
                      "candies": (1.0, 1.0, 0.55)}[kind]
        sx *= rng.uniform(0.95, 1.05)
        for v in bm.verts:
            x, y, z = v.co.x * sx, v.co.y * sy, v.co.z * sz
            if kind == "beans":                          # kidney: bend the long axis
                y -= 0.14 * (1 - (2 * x) ** 2)
            if kind == "coffee_beans":
                if z > 0:                                 # the flat face with its centre groove
                    z *= 0.55
                    z -= 0.11 * math.exp(-(y / 0.045) ** 2) * (1 - (2 * x) ** 2)   # a visible centre crease (clip r1)
            v.co = (x, y, z)
    elif kind == "ice":
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = (v.co.x * rng.uniform(0.92, 1.0), v.co.y * rng.uniform(0.9, 1.0), v.co.z * 0.85)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.14, segments=r["bevel"], affect="EDGES", profile=0.5)
    elif kind == "gems":
        n = 8
        girdle = [bm.verts.new((0.5 * math.cos(2 * math.pi * i / n), 0.5 * math.sin(2 * math.pi * i / n), 0.0))
                  for i in range(n)]
        table = [bm.verts.new((0.28 * math.cos(2 * math.pi * (i + 0.5) / n),
                               0.28 * math.sin(2 * math.pi * (i + 0.5) / n), 0.18)) for i in range(n)]
        culet = bm.verts.new((0.0, 0.0, -0.43))
        bm.faces.new(table)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((girdle[i], girdle[j], table[i]))
            bm.faces.new((table[i], girdle[j], table[j]))
            bm.faces.new((girdle[j], girdle[i], culet))
    elif kind == "coins":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=r["coin"], radius1=0.5, radius2=0.5, depth=0.075)
        rims = [e for e in bm.edges if all(abs(abs(v.co.z) - 0.0375) < 1e-6 for v in e.verts)
                and abs(e.verts[0].co.xy.length - 0.5) < 1e-6 and abs(e.verts[1].co.xy.length - 0.5) < 1e-6]
        bmesh.ops.bevel(bm, geom=rims, offset=0.012, segments=2, affect="EDGES", profile=0.5)
    elif kind == "pills":
        rad, half = 0.21, 0.5 - 0.21
        bmesh.ops.create_uvsphere(bm, u_segments=r["u"], v_segments=r["v"] | 1, radius=rad)   # odd: no ring on the equator
        for v in bm.verts:                                # poles onto X, then the halves pulled apart along X
            x, y, z = v.co.z, v.co.x, v.co.y
            v.co = (x + (half if x > 0 else -half), y, z)
    elif kind == "pebbles":                              # a chipped stone: noise, then flat facets cut by planes
        bmesh.ops.create_icosphere(bm, subdivisions=r["ico"], radius=0.5)
        ph = [rng.uniform(0, 6.3) for _ in range(6)]
        cuts = []
        for _ in range(7):
            z, a = rng.uniform(-1, 1), rng.uniform(0, 2 * math.pi)
            r = math.sqrt(1 - z * z)
            cuts.append(((r * math.cos(a), r * math.sin(a), z), rng.uniform(0.3, 0.42)))
        for v in bm.verts:
            x, y, z = v.co
            k = 1 + 0.12 * math.sin(3 * x + ph[0]) * math.sin(4 * y + ph[1]) + 0.08 * math.sin(6 * z + ph[2])
            p = [x * k, y * k * 0.85, z * k * 0.6]
            for n, d in cuts:
                s = p[0] * n[0] + p[1] * n[1] + p[2] * n[2]
                if s > d:
                    p = [p[i] - (s - d) * n[i] for i in range(3)]
            v.co = p
    elif kind == "shards":                               # an irregular convex flake, thicker at the middle
        n = rng.randint(5, 7)
        angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
        rim = [(0.5 * rng.uniform(0.55, 1.0) * math.cos(a), 0.5 * rng.uniform(0.35, 0.7) * math.sin(a)) for a in angs]
        top = [bm.verts.new((x, y, 0.035)) for x, y in rim]
        bot = [bm.verts.new((x * 0.97, y * 0.97, -0.035)) for x, y in rim]
        bm.faces.new(top)
        bm.faces.new(list(reversed(bot)))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((top[i], bot[i], bot[j], top[j]))
    elif kind == "leaves_dry":                           # a curled leaf: an ellipse blade with a midrib fold
        bmesh.ops.create_grid(bm, x_segments=14, y_segments=8, size=0.5)
        curl = rng.uniform(0.15, 0.3)
        for v in bm.verts:
            x, y = v.co.x, v.co.y * 0.55
            w = max(0.0, 1 - (2 * x) ** 2) ** 0.5
            y *= w
            z = curl * (y / 0.28) ** 2 * 0.3 + 0.06 * math.sin(3 * x + rng.uniform(0, 0.2)) - 0.08 * (2 * x) ** 2
            v.co = (x, y, z)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
        bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=0.012)
    else:
        raise KeyError(kind)
    _fit(bm, size * (1.0 if lod == "render" else COLLIDE_PAD.get(kind, 1.0)))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = _bm_to_mesh(bpy, bm, name)
    if kind in ("gems", "coins"):
        for p in me.polygons:
            p.use_smooth = kind == "coins" and abs(p.normal.z) < 0.5
    return me


def piece_material(kind):
    import bpy
    name = f"valora_piece_{kind}"
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    col, rough, metal, trans, sss, coat = PRESETS[kind]
    sh.inputs["Base Color"].default_value = (*col, 1.0)
    sh.inputs["Roughness"].default_value = rough
    sh.inputs["Metallic"].default_value = metal
    sh.inputs["Transmission Weight"].default_value = trans
    sh.inputs["Subsurface Weight"].default_value = sss
    sh.inputs["Coat Weight"].default_value = coat
    if kind == "ice":
        sh.inputs["IOR"].default_value = 1.31
    if kind == "gems":
        sh.inputs["IOR"].default_value = 2.42
    return m


def piece_object(scene, kind, size, variant, name, tag, lod="render"):
    import bpy
    me = piece_mesh(kind, size, variant, lod)
    if not me.materials:
        me.materials.append(piece_material(kind))
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob["valora_block"] = tag
    ob.rotation_mode = "QUATERNION"
    return ob


def _fcurve(act, ob, path, index):
    if hasattr(act, "fcurve_ensure_for_datablock"):
        return act.fcurve_ensure_for_datablock(ob, path, index=index)
    return act.fcurves.new(path, index=index)


def key_rows(ob, first_frame, rows, scale=None):
    """Key ob's location and rotation_quaternion from rigid_keys rows (x, y, z, qw, qx, qy, qz), row i at
    first_frame + i, LINEAR (object motion blur reads the keys), constant past both ends."""
    import bpy
    ob.rotation_mode = "QUATERNION"
    if scale is not None:
        ob.scale = (scale, scale, scale)
    ob.animation_data_create()
    act = bpy.data.actions.new(f"{ob.name}_keys")
    ob.animation_data.action = act
    n = len(rows)
    frames = [float(first_frame + i) for i in range(n)]
    for path, lo, count in (("location", 0, 3), ("rotation_quaternion", 3, 4)):
        for i in range(count):
            fc = _fcurve(act, ob, path, i)
            kps = fc.keyframe_points
            kps.add(n)
            co = [0.0] * (2 * n)
            co[0::2] = frames
            co[1::2] = [r[lo + i] for r in rows]
            kps.foreach_set("co", co)
            try:
                kps.foreach_set("interpolation", [1] * n)     # 'LINEAR'
            except (TypeError, RuntimeError):
                for kp in kps:
                    kp.interpolation = "LINEAR"
            for kp in kps:
                kp.handle_left_type = kp.handle_right_type = "VECTOR"
            fc.extrapolation = "CONSTANT"
            fc.update()
    ob.location, ob.rotation_quaternion = rows[0][:3], rows[0][3:7]


# ---------------------------------------------------------------- the lane's Bullet helpers (bake only)
SUBSTEPS, ITERATIONS = 60, 20        # METHODS RB-05; with use_margin + margin 0 a piece rests exactly (formats.py)


def rigid_world(scene, frames, time_scale):
    import bpy
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    w = scene.rigidbody_world
    w.substeps_per_frame, w.solver_iterations = SUBSTEPS, ITERATIONS
    w.time_scale = float(time_scale)
    # Force fields stay out of the rigid world: a wind field's flow acts as air drag, and on gram-scale pieces
    # it pins them at a terminal speed of millimetres per second (measured 2026-09-28: beans drifted instead of
    # falling). Gravity has its own weight and stays on.
    import bpy
    none = bpy.data.collections.get("valora_rigid_no_fields") or bpy.data.collections.new("valora_rigid_no_fields")
    w.effector_weights.collection = none           # an empty effector collection: no field reaches the pieces
    w.point_cache.frame_start, w.point_cache.frame_end = frames["bake_first"], frames["bake_last"]
    return w


def _add(obs, kind):
    import bpy
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.rigidbody.objects_add(type=kind)
    for o in obs:
        o.rigid_body.use_margin, o.rigid_body.collision_margin = True, 0.0


def ground_slab(profile):
    """A passive box whose top face is the ground (z = 0), wide enough for anything that rolls off. Built from
    data (no operator), so no context or 3D-cursor state can move it."""
    import bmesh
    import bpy
    half = max(3.0, 6.0 * profile.longest)
    depth = max(0.05, 0.1 * profile.longest)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * 2 * half, v.co.y * 2 * half, v.co.z * depth)
    me = bpy.data.meshes.new("valora_rigid_ground")
    bm.to_mesh(me)
    bm.free()
    g = bpy.data.objects.new("valora_rigid_ground", me)
    bpy.context.scene.collection.objects.link(g)
    g.location = (profile.center[0], profile.center[1], -depth / 2)
    bpy.context.view_layer.update()
    _add([g], "PASSIVE")
    g.rigid_body.collision_shape = "BOX"
    g.rigid_body.friction = 0.7
    return g


def passive(obs, shape="MESH", friction=0.6, restitution=0.2, animated=False):
    obs = obs if isinstance(obs, list) else [obs]
    _add(obs, "PASSIVE")
    for o in obs:
        rb = o.rigid_body
        rb.collision_shape = shape
        rb.friction, rb.restitution = friction, restitution
        rb.kinematic = animated
    return obs


def active(obs, kind, sizes, start_asleep=False):
    """Pieces as ACTIVE convex hulls with the kind's friction, restitution and a real mass (density x hull-ish
    volume), low deactivation thresholds (a resting pile goes quiet instead of creeping)."""
    _add(obs, "ACTIVE")
    for o, s in zip(obs, sizes):
        rb = o.rigid_body
        rb.collision_shape = "CONVEX_HULL"
        rb.friction = FRICTION.get(kind, 0.6)
        rb.restitution = RESTITUTION.get(kind, 0.2)
        rb.mass = max(1e-5, DENSITY.get(kind, 1500) * 0.35 * s ** 3)
        rb.linear_damping, rb.angular_damping = 0.04, 0.3
        rb.use_deactivation = True
        rb.deactivate_linear_velocity, rb.deactivate_angular_velocity = 0.02, 0.3
        rb.use_start_deactivated = start_asleep


def record(scene, obs, frames):
    """Step Bullet with frame_set over the bake range and return {name: rows} (rigid_keys rows, sign-continuous
    quaternions). bake_to_keyframes does not work headless (formats.py)."""
    from engine.physics.scatter import continuous_quats, row
    rows = {o.name: [] for o in obs}
    for f in range(frames["bake_first"], frames["bake_last"] + 1):
        scene.frame_set(f)
        for o in obs:
            m = o.matrix_world
            rows[o.name].append(row(m.to_translation(), m.to_quaternion()))
    return {k: continuous_quats(v) for k, v in rows.items()}


def key_pieces(ctx, keys, tag, build_one):
    """build(): one object per baked piece (build_one(name, info) makes it), keyed from the rows at render frame =
    bake frame + offset; rows before the clip start (pre-roll) are dropped and the location curves extrapolate
    LINEAR backwards, so a piece in flight at the window start enters the frame on its baked velocity instead of
    hanging in the air; after the last key everything holds."""
    b = ctx.bake
    fr = b["frames"]
    first, off = keys["frames"][0], fr["offset"]
    skip = max(0, fr["clip_first"] - (first + off))
    out = []
    for name, rows in keys["pieces"].items():
        ob = build_one(name)
        ob["valora_block"] = tag
        rows = rows[skip:]
        rows = rows + [rows[-1]]                     # a flat last segment: nothing drifts after the window
        key_rows(ob, first + off + skip, rows, scale=(keys.get("info", {}).get("scale") or {}).get(name))
        act = ob.animation_data.action
        from engine.blender.realism_rig import fcurves
        for c in fcurves(act):
            if c.data_path == "location":
                c.extrapolation = "LINEAR"
        out.append(ob)
    return out
