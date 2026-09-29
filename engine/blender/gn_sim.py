"""The shared Geometry Nodes point sim (phase 6 Task 103). Runs inside Blender only.

One node group per sim, with a Simulation zone that
- SPAWNS: adds the particles born in this frame from an emitter mesh (one vertex per particle, made by
  emitter_object from engine/physics/gn_sim's seeded maths: attributes birth, velocity, size, life, age and
  the block's extras), so the rate, the layout and every random draw are decided on the host, seeded;
- MOVES (per substep, a Repeat zone): gravity, linear drag k (v - wind), and wind from the ONE shared group
  `valora_wind` (engine/blender/wind_field, H4) scaled by the block's response, never its own noise; or the
  block's own `step` hook (runners: a surface-constrained walk);
- COLLIDES: a ray cast along the step against the proxy shell (so a fast spark cannot tunnel a thin wall),
  then a push-out along the nearest proxy face's normal for anything still inside (on a closed shell that is
  the SDF-gradient push-out: the T99 inside test uses the same rule), and the ground plane z = ground; both
  with restitution and friction;
- AGES AND KILLS: age += dt, deleted past its life;
- always carries `velocity` (m/s, METHODS R7: Cycles motion blur), `age` and `size`.

The bake (bake_sim_object) runs geometry_node_bake_single with bake_target 'DISK', use_custom_path, the
directory and a custom frame range = the ABSOLUTE bake range (engine/bake/window: GN has no frame-offset API,
so pre-roll runs in zero or negative frames). The compile's build calls sim_object with the same directory and
range: the zone reads the cache and never simulates, and SimInCompile passes because all three bake settings
are set.

Node idnames used (Blender 5.0.1): GeometryNodeSimulationInput/Output, GeometryNodeRepeatInput/Output,
GeometryNodeMeshToPoints, GeometryNodeRaycast, GeometryNodeProximity, GeometryNodeSampleNearestSurface,
GeometryNodeSetPointRadius, GeometryNodeDeleteGeometry, GeometryNodeJoinGeometry, GeometryNodeObjectInfo."""
import bpy

from engine.blender.gn import Tree

SKIN_M = 0.0005          # how far a collided point is set off the surface (0.5 mm; real-size droplets are >= 0.2 mm)
BUILTIN = ("birth", "velocity", "size", "life", "age")


def emitter_object(name, particles, extras=()):
    """A hidden mesh with one loose vertex per particle at its birth position, carrying birth (frame), velocity,
    size, life (s), age (0) and each extra (a float, or a 3-tuple for a vector) as point attributes."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p["pos"]) for p in particles], [], [])
    for key in BUILTIN + tuple(extras):
        if key == "age":
            vals = [0.0] * len(particles)
        else:
            vals = [p["vel" if key == "velocity" else key] for p in particles]
        vec = bool(particles) and isinstance(vals[0], (tuple, list))
        a = me.attributes.new(key, "FLOAT_VECTOR" if vec else "FLOAT", "POINT")
        if particles:
            if vec:
                a.data.foreach_set("vector", [float(c) for v in vals for c in v])
            else:
                a.data.foreach_set("value", [float(v) for v in vals])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


def _obj_geo(t, obj, space="RELATIVE"):
    n = t.node("GeometryNodeObjectInfo", transform_space=space)
    t.feed(n.inputs["Object"], obj)
    return n.outputs["Geometry"]


def _reflect(t, v, n, restitution, friction):
    """v with its normal part reversed x restitution and its tangential part x (1 - friction)."""
    vn = t.vmath("SCALE", n, scale=t.vmath("DOT_PRODUCT", v, n))
    vt = t.vmath("SUBTRACT", v, vn)
    return t.vmath("SUBTRACT", t.vmath("SCALE", vt, scale=1.0 - friction), t.vmath("SCALE", vn, scale=restitution))


def _and(t, a, b):
    return t.math("MULTIPLY", a, b)


def collide_proxy(t, proxy_geo, p0, p1, v1, h, restitution, friction):
    """(p, v) after the step p0 -> p1 at velocity v1 against a closed proxy: a ray cast along the step
    (entering hits only), then a push-out for any point still inside (nearest face normal points away)."""
    rc = t.node("GeometryNodeRaycast")
    t.feed(rc.inputs["Target Geometry"], proxy_geo)
    t.feed(rc.inputs["Source Position"], p0)
    t.feed(rc.inputs["Ray Direction"], t.vmath("NORMALIZE", v1))
    t.feed(rc.inputs["Ray Length"], t.math("ADD", t.math("MULTIPLY", t.vmath("LENGTH", v1), h), SKIN_M))
    hn = rc.outputs["Hit Normal"]
    hit = _and(t, rc.outputs["Is Hit"], t.math("LESS_THAN", t.vmath("DOT_PRODUCT", v1, hn), 0.0))
    p2 = t.switch_vec(hit, p1, t.vmath("ADD", rc.outputs["Hit Position"], t.vmath("SCALE", hn, scale=SKIN_M)))
    v2 = t.switch_vec(hit, v1, _reflect(t, v1, hn, restitution, friction))
    prox = t.node("GeometryNodeProximity")
    t.feed(prox.inputs[0], proxy_geo)
    t.feed(prox.inputs["Source Position"], p2)
    q = prox.outputs["Position"]
    sn = t.node("GeometryNodeSampleNearestSurface", data_type="FLOAT_VECTOR")
    t.feed(sn.inputs["Mesh"], proxy_geo)
    t.feed(next(s for s in sn.inputs if s.name == "Value" and s.enabled), t.node("GeometryNodeInputNormal").outputs[0])
    t.feed(sn.inputs["Sample Position"], p2)
    n2 = next(s for s in sn.outputs if s.name == "Value" and s.enabled)
    inside = t.math("LESS_THAN", t.vmath("DOT_PRODUCT", t.vmath("SUBTRACT", p2, q), n2), 0.0)
    p3 = t.switch_vec(inside, p2, t.vmath("ADD", q, t.vmath("SCALE", n2, scale=SKIN_M)))
    v3 = t.switch_vec(inside, v2, _reflect(t, v2, n2, restitution, friction))
    return p3, v3


def collide_ground(t, p, v, ground_z, restitution, friction):
    x, y, z = t.xyz(p)
    vx, vy, vz = t.xyz(v)
    below = t.math("LESS_THAN", z, ground_z)
    p2 = t.vec(x, y, t.math("MAXIMUM", z, ground_z))
    bounced = t.vec(t.math("MULTIPLY", vx, 1.0 - friction), t.math("MULTIPLY", vy, 1.0 - friction),
                    t.math("MULTIPLY", t.math("ABSOLUTE", vz), restitution))
    return p2, t.switch_vec(below, v, bounced)


def free_step(t, h, forces, collide):
    """One ballistic substep of length h (a float socket, seconds) over t.geometry."""
    p0 = t.position()
    v0 = t.attr("velocity", "FLOAT_VECTOR")
    acc = t.vec(*forces.get("gravity", (0.0, 0.0, -9.81)))
    k = float(forces.get("drag", 0.0))
    if k:
        air = t.vec(0.0, 0.0, 0.0)
        ng = bpy.data.node_groups.get("valora_wind")
        if ng is not None and forces.get("wind", 0.0):
            air = t.vmath("SCALE", t.group(ng, Position=p0).outputs["Wind"], scale=float(forces["wind"]))
        acc = t.vmath("ADD", acc, t.vmath("SCALE", t.vmath("SUBTRACT", air, v0), scale=k))
    v1 = t.vmath("ADD", v0, t.vmath("SCALE", acc, scale=h))
    p1 = t.vmath("ADD", p0, t.vmath("SCALE", v1, scale=h))
    e, mu = float(collide.get("restitution", 0.2)), float(collide.get("friction", 0.3))
    if collide.get("proxy") is not None:
        p1, v1 = collide_proxy(t, _obj_geo(t, collide["proxy"]), p0, p1, v1, h, e, mu)
    if collide.get("ground") is not None:
        p1, v1 = collide_ground(t, p1, v1, float(collide["ground"]), e, mu)
    commit(t, p1, v1)


def commit(t, p, v):
    """Write the new position and velocity from fields evaluated on the SAME (pre-step) geometry."""
    t.store("_np", p, "FLOAT_VECTOR")
    t.store("velocity", v, "FLOAT_VECTOR")
    t.set_position(t.attr("_np", "FLOAT_VECTOR"))


def ensure_point_sim(name, *, spawn, forces, collide, life=None, attrs=(), post=None, substeps=1, time_scale=1.0,
                     step=None):
    """The node group `name` (rebuilt if it exists). spawn: the emitter object or None (a build that only reads the
    cache); forces: {"gravity": (x, y, z), "drag": k per s, "wind": response 0..1}; collide: {"proxy": object or
    None, "ground": z or None, "restitution", "friction"}; life: unused (each particle carries its own, kept for
    the plan's signature); attrs: the extra attribute names (documentation: the emitter carries them through);
    post(t): nodes after the zone (radius, material, instancing); step(t, h): replaces free_step."""
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    t = Tree(name)
    t.ng.name = name
    si = t.node("GeometryNodeSimulationInput")
    so = t.node("GeometryNodeSimulationOutput")
    si.pair_with_output(so)
    frame = t.node("GeometryNodeInputSceneTime").outputs["Frame"]
    born = None
    if spawn is not None:
        m2p = t.node("GeometryNodeMeshToPoints")
        t.feed(m2p.inputs["Mesh"], _obj_geo(t, spawn, "ORIGINAL"))
        birth = t.attr("birth")
        sel = _and(t, t.math("GREATER_THAN", birth, t.math("SUBTRACT", frame, 1.0 - 1e-4)),
                   t.math("LESS_THAN", birth, t.math("ADD", frame, 1e-4)))
        t.feed(m2p.inputs["Selection"], sel)
        born = m2p.outputs["Points"]
    join = t.node("GeometryNodeJoinGeometry")
    t.ng.links.new(si.outputs["Geometry"], join.inputs[0])
    if born is not None:
        t.ng.links.new(born, join.inputs[0])
    dt = t.math("MULTIPLY", si.outputs["Delta Time"], float(time_scale))
    ri = t.node("GeometryNodeRepeatInput")
    ro = t.node("GeometryNodeRepeatOutput")
    ri.pair_with_output(ro)
    ri.inputs["Iterations"].default_value = int(max(1, substeps))
    t.ng.links.new(join.outputs[0], ri.inputs["Geometry"])
    t.geometry = ri.outputs["Geometry"]
    h = t.math("DIVIDE", dt, float(max(1, substeps)))
    (step or (lambda tt, hh: free_step(tt, hh, forces, collide)))(t, h)
    t.ng.links.new(t.geometry, ro.inputs["Geometry"])
    t.geometry = ro.outputs["Geometry"]
    t.store("age", t.math("ADD", t.attr("age"), dt))
    dead = t.node("GeometryNodeDeleteGeometry", domain="POINT")
    t.feed(dead.inputs["Geometry"], t.geometry)
    t.feed(dead.inputs["Selection"], t.math("GREATER_THAN", t.attr("age"), t.attr("life")))
    t.ng.links.new(dead.outputs["Geometry"], so.inputs["Geometry"])
    t.geometry = so.outputs["Geometry"]
    if post is not None:
        post(t)
    else:
        radius(t)
    return t.finish()


FLOOR_SHORT_SIDE = 540     # size floors (a sub-pixel point drawn at least this wide) are set for this short side


def floor_scale():
    """FLOOR_SHORT_SIDE / the render's short side: 1 at the preview tier, 0.5 at final 1080p. A floor in metres that
    made a sub-pixel droplet or spark one 540p pixel wide is halved at 1080p instead of drawing it 2 px wide (hero
    pass 2026-09-28: the final-tier frames were full of oversized beads)."""
    r = bpy.context.scene.render
    short = min(r.resolution_x, r.resolution_y) * r.resolution_percentage / 100.0
    return FLOOR_SHORT_SIDE / max(short, 1.0)


def radius(t, scale=0.5):
    """Point radius = size x scale (Cycles renders a point cloud as spheres of this radius)."""
    n = t.node("GeometryNodeSetPointRadius")
    t.feed(n.inputs["Points"], t.geometry)
    t.feed(n.inputs["Radius"], t.math("MULTIPLY", t.attr("size"), scale))
    t.geometry = n.outputs["Points"]


def material(t, mat):
    n = t.node("GeometryNodeSetMaterial")
    t.feed(n.inputs["Geometry"], t.geometry)
    n.inputs["Material"].default_value = mat
    t.geometry = n.outputs["Geometry"]


def sim_object(name, ng, bake_dir, frames, block, data="POINTCLOUD"):
    """The object that carries the sim: an empty point cloud (data="POINTCLOUD", so the evaluated object data IS the
    simulated points and simProbe reads their positions and velocity) or an empty mesh (data="MESH", for a group
    that realizes instanced cards into a mesh), with the node group and its one simulation bake on DISK at
    `bake_dir` over the absolute range frames["bake_first"]..frames["bake_last"]. Tagged valora_block = block."""
    me = bpy.data.pointclouds.new(name) if data == "POINTCLOUD" else bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob["valora_block"] = block
    mod = ob.modifiers.new("valora_gn_sim", "NODES")
    mod.node_group = ng
    for b in mod.bakes:
        b.bake_target = "DISK"
        b.use_custom_path = True
        b.directory = str(bake_dir)
        b.use_custom_simulation_frame_range = True
        b.frame_start, b.frame_end = int(frames["bake_first"]), int(frames["bake_last"])
    return ob


def bake_sim_object(ob):
    """Bake every simulation bake of the object to its directory (geometry_node_bake_single, formats.gn_disk)."""
    mod = ob.modifiers["valora_gn_sim"]
    out = []
    for b in mod.bakes:
        with bpy.context.temp_override(object=ob, active_object=ob):
            out.append(str(bpy.ops.object.geometry_node_bake_single(session_uid=ob.session_uid,
                                                                     modifier_name=mod.name, bake_id=b.bake_id)))
    if any(r != "{'FINISHED'}" for r in out):
        raise RuntimeError(f"GN bake of {ob.name} failed: {out}")
    return out


def read_points(ob, frame, names=("velocity", "age", "size")):
    """The evaluated points of a sim object at `frame`: {"position": [...], name: [...]} (world space; the
    object sits at identity). Tests and probes only."""
    bpy.context.scene.frame_set(int(frame))
    g = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
    pc = g.pointcloud
    out = {"position": []}
    if pc is None:
        return out
    out["position"] = [tuple(d.vector) for d in pc.attributes["position"].data]
    for n in names:
        a = pc.attributes.get(n)
        if a is None:
            out[n] = None
        else:
            out[n] = [tuple(d.vector) if hasattr(d, "vector") else d.value for d in a.data]
    return out
