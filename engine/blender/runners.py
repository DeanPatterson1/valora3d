"""The `runners` GN step (phase 6 Task 104, FL-04 + FL-20 drips). Runs inside Blender only; maths in
engine/physics/runners.py, the shared zone in engine/blender/gn_sim.py (ensure_point_sim's `step` hook).

Per substep h, for every point of the zone:
- a TRAIL point (trail = 1) stays where it was left, velocity 0;
- a RUNNER on the surface (free = 0) reads the render mesh's nearest surface normal n0 (Sample Nearest Surface on
  the upload's evaluated meshes through Object Info: read-only, the upload gets no modifier), moves along the
  tangential gravity g - (g.n0)n0 at its speed x the slope while its stick-slip schedule says it runs, and is
  re-projected onto the surface (Geometry Proximity) SKIN_M off it. Where the surface turns away (the new normal
  n1 has dot(n0, n1) < EDGE_DOT: a convex edge) or faces down (n1.z < DETACH_NZ) it lets go: free = 1, leaving
  with its run velocity;
- a free DRIP falls ballistically (gravity, no drag at mm scale over < 0.3 m) and is gone at the ground
  (life = 0, so the zone's ageing deletes it);
- a moving runner that has travelled TRAIL_STEP_M since its last trail point drops a new one there (a wet streak
  of TRAIL_W_M beads, TRAIL_LIFT_M off the surface), so the streak's density follows the distance run, not time.
Every point carries velocity (m/s) for motion blur."""
import bpy

from engine.blender import gn_sim as G
from engine.physics import runners as R

TRAIL_W_M = 0.0011       # the wet streak's width (a 1.1 mm streak behind a 1.5-4 mm drop) (eng)
TRAIL_STEP_M = 0.0005    # one streak bead per 0.5 mm run: the 1.1 mm beads overlap into a continuous streak
TRAIL_LIFT_M = 0.00025   # a streak bead's centre off the surface (it is a film, flatter than a drop)
TRAIL_LIFE_S = 1.0e6     # a streak stays for the clip


def world_triangles(meshes):
    """(verts, tris, normals) of the subject's evaluated meshes in world metres (the seeding input)."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, tris, normals = [], [], []
    for m in meshes:
        if m.type != "MESH":
            continue
        ev = m.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        mw = m.matrix_world
        nm = mw.to_3x3().inverted_safe().transposed()
        base = len(verts)
        verts.extend(tuple(mw @ v.co) for v in me.vertices)
        for lt in me.loop_triangles:
            tris.append(tuple(base + i for i in lt.vertices))
            normals.append(tuple((nm @ lt.normal).normalized()))
        ev.to_mesh_clear()
    return verts, tris, normals


def _surface(t, meshes):
    """The upload's evaluated meshes joined, in the sim object's space (it sits at identity: world), with their
    true face normals (custom split normals removed)."""
    join = t.node("GeometryNodeJoinGeometry")
    for m in meshes:
        info = t.node("GeometryNodeObjectInfo", transform_space="RELATIVE")
        info.inputs["Object"].default_value = m
        t.ng.links.new(info.outputs["Geometry"], join.inputs[0])
    rm = t.node("GeometryNodeRemoveAttribute")
    t.feed(rm.inputs["Geometry"], join.outputs[0])
    rm.inputs["Name"].default_value = "custom_normal"
    return rm.outputs["Geometry"]


def _nearest_normal(t, surf, p):
    sn = t.node("GeometryNodeSampleNearestSurface", data_type="FLOAT_VECTOR")
    t.feed(sn.inputs["Mesh"], surf)
    t.feed(next(s for s in sn.inputs if s.name == "Value" and s.enabled), t.node("GeometryNodeInputNormal").outputs[0])
    t.feed(sn.inputs["Sample Position"], p)
    return t.vmath("NORMALIZE", next(s for s in sn.outputs if s.name == "Value" and s.enabled))


def _nearest_point(t, surf, p):
    prox = t.node("GeometryNodeProximity")
    t.feed(prox.inputs[0], surf)
    t.feed(prox.inputs["Source Position"], p)
    return prox.outputs["Position"]


def _gt(a, b):
    return ("GREATER_THAN", a, b)


def make_step(meshes, ground_z, trail=True):
    """step(t, h) for ensure_point_sim."""

    def step(t, h):
        m = t.math
        surf = _surface(t, meshes)
        pre = t.geometry
        p0 = t.position()
        v0 = t.attr("velocity", "FLOAT_VECTOR")
        is_trail = m("GREATER_THAN", t.attr("trail"), 0.5)
        is_free = m("GREATER_THAN", t.attr("free"), 0.5)
        n0 = _nearest_normal(t, surf, p0)
        cyc = m("ADD", t.attr("pause"), t.attr("move"))
        run = m("GREATER_THAN", m("FLOORED_MODULO", m("ADD", t.attr("age"), t.attr("phase")), cyc),
                m("SUBTRACT", t.attr("pause"), 1e-6))
        # tangential gravity g - (g.n)n, times speed / g (= direction x speed x slope), while running
        gn = m("MULTIPLY", t.xyz(n0)[2], -R.G)
        gt = t.vmath("SUBTRACT", t.vec(0.0, 0.0, -R.G), t.vmath("SCALE", n0, scale=gn))
        vrun = t.vmath("SCALE", gt, scale=m("MULTIPLY", m("DIVIDE", t.attr("speed"), R.G), run))
        p1 = t.vmath("ADD", p0, t.vmath("SCALE", vrun, scale=h))
        n1 = _nearest_normal(t, surf, p1)
        prun = t.vmath("ADD", _nearest_point(t, surf, p1), t.vmath("SCALE", n1, scale=R.SKIN_M))
        edge = m("LESS_THAN", t.vmath("DOT_PRODUCT", n0, n1), R.EDGE_DOT)
        under = m("LESS_THAN", t.xyz(n1)[2], R.DETACH_NZ)
        det = m("MAXIMUM", edge, under)
        # a free drip: ballistic, gone at the ground
        vb = t.vmath("ADD", v0, t.vmath("SCALE", t.vec(0.0, 0.0, -R.G), scale=h))
        pb = t.vmath("ADD", p0, t.vmath("SCALE", vb, scale=h))
        landed = m("MULTIPLY", is_free, m("LESS_THAN", t.xyz(pb)[2], ground_z + R.SKIN_M))
        vstick = t.vmath("SCALE", t.vmath("SUBTRACT", prun, p0), scale=m("DIVIDE", 1.0, h))
        # a runner never climbs: a re-projection that would lift it (a ledge's corner, a smooth-normal/face
        # mismatch) is refused and the drop stays pinned where it is (it pools against the ledge)
        climb = m("GREATER_THAN", t.xyz(prun)[2], t.xyz(p0)[2])
        stay = m("MULTIPLY", climb, m("SUBTRACT", 1.0, det))
        p_on = t.switch_vec(stay, t.switch_vec(det, prun, p1), p0)
        v_on = t.switch_vec(stay, t.switch_vec(det, vstick, vrun), t.vec(0.0, 0.0, 0.0))
        p_new = t.switch_vec(is_trail, t.switch_vec(is_free, p_on, pb), p0)
        v_new = t.switch_vec(is_trail, t.switch_vec(is_free, v_on, vb), t.vec(0.0, 0.0, 0.0))
        f_new = m("MULTIPLY", m("SUBTRACT", 1.0, is_trail), m("MAXIMUM", is_free, det))
        life_new = m("MULTIPLY", t.attr("life"), m("SUBTRACT", 1.0, landed))
        lt = t.attr("_lt", "FLOAT_VECTOR")
        drop = m("MULTIPLY", m("MULTIPLY", m("SUBTRACT", 1.0, is_trail), m("SUBTRACT", 1.0, is_free)),
                 m("MULTIPLY", run, m("GREATER_THAN", t.vmath("DISTANCE", p0, lt), TRAIL_STEP_M)))
        if trail:
            dup = t.node("GeometryNodeDuplicateElements", domain="POINT")
            t.feed(dup.inputs["Geometry"], pre)
            t.feed(dup.inputs["Selection"], drop)
            t.geometry = dup.outputs["Geometry"]
            t.set_position(t.vmath("SUBTRACT", t.position(), t.vmath("SCALE", _nearest_normal(t, surf, t.position()),
                                                                    scale=R.SKIN_M - TRAIL_LIFT_M)))
            t.store("velocity", (0.0, 0.0, 0.0), "FLOAT_VECTOR")
            t.store("trail", 1.0)
            t.store("size", TRAIL_W_M)
            t.store("life", TRAIL_LIFE_S)
            streak = t.geometry
            t.geometry = pre
        t.store("_nf", f_new)
        t.store("_nl", life_new)
        t.store("_nlt", t.switch_vec(m("GREATER_THAN", drop, 0.5), lt, p0), "FLOAT_VECTOR")
        G.commit(t, p_new, v_new)
        t.store("free", t.attr("_nf"))
        t.store("life", t.attr("_nl"))
        t.store("_lt", t.attr("_nlt", "FLOAT_VECTOR"), "FLOAT_VECTOR")
        if trail:
            j = t.node("GeometryNodeJoinGeometry")
            t.ng.links.new(t.geometry, j.inputs[0])
            t.ng.links.new(streak, j.inputs[0])
            t.geometry = j.outputs[0]

    return step


def water():
    """Clear water for the drops and the streak (the droplets effect's recipe: transmission 1, IOR 1.333)."""
    from engine.blender import weather_nodes as wn
    m = bpy.data.materials.get("valora_runners_water") or wn.water("valora_runners_water")
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Roughness"].default_value = 0.015
    sh.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    return m


def ensure(ctx, spawn):
    """The runners node group: the shared zone with this step, points rendered as water spheres of the drop's
    size (radius = size / 2)."""
    p = ctx.params
    ground = 0.0
    mat = water()

    def post(t):
        G.radius(t, 0.5)
        G.material(t, mat)

    return G.ensure_point_sim("valora_runners", spawn=spawn, forces={}, collide={}, post=post,
                              substeps=R.SUBSTEPS, time_scale=float(p["timeScale"]),
                              step=make_step(list(ctx.meshes), ground, bool(p.get("trail", True))),
                              attrs=R.EXTRAS)
