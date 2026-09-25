"""Shared stateless weather Geometry Nodes (plan Task 64). Runs inside Blender only.

Everything here is a function of (scene time, seed, params, the camera and subject transforms): no
simulation zone, no bake, no frame that depends on the one before (METHODS R1), so preview equals final and
any frame range renders anywhere.

box_points: N seeded points on a world-fixed lattice, advanced analytically by a drift field and wrapped into
a square box that follows the active camera (Scene Time x velocity, Wrap per axis). A point stays still in
the world between wraps, so it streaks from its own velocity, and a wrap only happens at a box face, far
from the view. shelter: deletes points inside the posed subject's footprint column below its top (Object
Info on valora_realism_offset, so shelter follows a moving subject) and points too close to the camera.
impact_events: seeded ground crowns, one per slot per period, the event index floor((t + phase) / period)
seeding its position, so every frame evaluates on its own.

Node idnames probed on Blender 5.0.1 (2026-09-25): GeometryNodePoints, FunctionNodeRandomValue,
GeometryNodeInputActiveCamera, GeometryNodeObjectInfo, GeometryNodeDeleteGeometry, GeometryNodeInstanceOnPoints,
GeometryNodeRealizeInstances, GeometryNodeMeshIcoSphere, GeometryNodeSetMaterial, GeometryNodeInputIndex,
FunctionNodeAlignRotationToVector, GeometryNodeCurvePrimitiveCircle, GeometryNodeCurveToMesh,
GeometryNodeDistributePointsOnFaces, GeometryNodeInputNormal, GeometryNodeExtrudeMesh, GeometryNodeJoinGeometry.
Nodes are created by type; sockets are found by identifier or availability, never by a localized name."""
import bpy

SHELTER = "valora_shelter"     # the delete node the probe mutes to count points before the shelter


def _avail(socks):
    return [s for s in socks if getattr(s, "enabled", True) and not getattr(s, "is_unavailable", False)]


def random(t, data_type, lo, hi, seed, ident=None):
    """A Random Value field (FLOAT or FLOAT_VECTOR) in [lo, hi], seeded; ident = the ID socket (default index)."""
    n = t.node("FunctionNodeRandomValue", data_type=data_type)
    ins = _avail(n.inputs)
    t.feed(ins[0], lo)
    t.feed(ins[1], hi)
    idsock = next(s for s in ins if s.name == "ID")
    if ident is not None:
        t.feed(idsock, ident)
    next(s for s in ins if s.name == "Seed").default_value = int(seed) % 2147483647
    return _avail(n.outputs)[0]


def _vertices(t, points):
    """A point cloud as mesh vertices: the evaluated object stays a mesh, so probes read it with to_mesh()."""
    n = t.node("GeometryNodePointsToVertices")
    t.feed(n.inputs["Points"], points)
    return n.outputs["Mesh"]


def index(t):
    return t.node("GeometryNodeInputIndex").outputs[0]


def camera_location(t):
    cam = t.node("GeometryNodeInputActiveCamera").outputs[0]
    info = t.node("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    t.feed(info.inputs["Object"], cam)
    return info.outputs["Location"]


def box_centre(t, subject_xy, cam_weight=0.5):
    """Between the active camera and the subject (xy): the camera sits inside a box of side >= its distance."""
    cx, cy, _ = t.xyz(camera_location(t))
    mix = lambda c, s: t.math("ADD", t.math("MULTIPLY", c, cam_weight), s * (1.0 - cam_weight))  # noqa: E731
    return mix(cx, subject_xy[0]), mix(cy, subject_xy[1])


def box_points(t, n, seed, side, height, centre, drift):
    """t.geometry becomes N points: base on [0, side]^2 x [0, height], plus the drift field (a vector socket,
    metres, usually velocity x Scene Time), wrapped into the box around `centre` (x, y sockets) and [0, height]."""
    pts = t.node("GeometryNodePoints")
    pts.inputs["Count"].default_value = int(n)
    pts.inputs["Radius"].default_value = 0.001
    t.feed(pts.inputs["Position"], random(t, "FLOAT_VECTOR", (0.0, 0.0, 0.0), (side, side, height), seed))
    t.geometry = _vertices(t, pts.outputs["Points"])
    qx, qy, qz = t.xyz(t.vmath("ADD", t.position(), drift))
    cx, cy = centre
    wx = t.math("WRAP", qx, t.math("ADD", cx, side / 2.0), t.math("SUBTRACT", cx, side / 2.0))
    wy = t.math("WRAP", qy, t.math("ADD", cy, side / 2.0), t.math("SUBTRACT", cy, side / 2.0))
    wz = t.math("WRAP", qz, height, 0.0)
    t.set_position(t.vec(wx, wy, wz))


def shelter(t, offset_obj, lo, hi, near_m=0.0, top=True):
    """Delete the points inside the posed subject's footprint (placed bounds lo/hi, xy) below its top (or at
    any height with top=False), and within near_m of the active camera."""
    rel = t.invert(t.object_transform(offset_obj))
    px, py, pz = t.xyz(t.point(t.position(), rel))
    inside = t.math("MULTIPLY", t.math("GREATER_THAN", px, lo[0]), t.math("LESS_THAN", px, hi[0]))
    inside = t.math("MULTIPLY", inside, t.math("MULTIPLY", t.math("GREATER_THAN", py, lo[1]), t.math("LESS_THAN", py, hi[1])))
    if top:
        inside = t.math("MULTIPLY", inside, t.math("LESS_THAN", pz, hi[2]))
    if near_m > 0.0:
        near = t.math("LESS_THAN", t.vmath("DISTANCE", t.position(), camera_location(t)), near_m)
        inside = t.math("MAXIMUM", inside, near)
    d = t.node("GeometryNodeDeleteGeometry")
    d.name = SHELTER
    t.feed(d.inputs["Geometry"], t.geometry)
    t.feed(d.inputs["Selection"], inside)
    t.geometry = d.outputs["Geometry"]


def store_vector(t, name, value):
    t.store(name, value, "FLOAT_VECTOR")


def instance(t, mesh_sock, scale, rotation=None, material=None, realize=True):
    """Instance a mesh on every point (scale: vector socket or tuple), optionally set its material and realize
    it, so point attributes (velocity) reach the rendered vertices (METHODS R7)."""
    if material is not None:
        sm = t.node("GeometryNodeSetMaterial")
        t.feed(sm.inputs["Geometry"], mesh_sock)
        sm.inputs["Material"].default_value = material
        mesh_sock = sm.outputs["Geometry"]
    iop = t.node("GeometryNodeInstanceOnPoints")
    t.feed(iop.inputs["Points"], t.geometry)
    t.feed(iop.inputs["Instance"], mesh_sock)
    t.feed(iop.inputs["Scale"], scale)
    if rotation is not None:
        t.feed(iop.inputs["Rotation"], rotation)
    t.geometry = iop.outputs["Instances"]
    if realize:
        r = t.node("GeometryNodeRealizeInstances")
        t.feed(r.inputs["Geometry"], t.geometry)
        t.geometry = r.outputs["Geometry"]


def align_z(t, vector):
    n = t.node("FunctionNodeAlignRotationToVector", axis="Z")
    t.feed(n.inputs["Vector"], vector)
    return n.outputs["Rotation"]


def ico(t, subdiv=1):
    s = t.node("GeometryNodeMeshIcoSphere")
    s.inputs["Radius"].default_value = 1.0
    s.inputs["Subdivisions"].default_value = subdiv
    return s.outputs["Mesh"]


def ring(t, tube=0.12):
    """A unit-radius torus (a crown or ripple ring), tube radius `tube`."""
    path, prof = t.node("GeometryNodeCurvePrimitiveCircle"), t.node("GeometryNodeCurvePrimitiveCircle")
    path.inputs["Resolution"].default_value, path.inputs["Radius"].default_value = 24, 1.0
    prof.inputs["Resolution"].default_value, prof.inputs["Radius"].default_value = 6, tube
    m = t.node("GeometryNodeCurveToMesh")
    t.feed(m.inputs["Curve"], path.outputs["Curve"])
    t.feed(m.inputs["Profile Curve"], prof.outputs["Curve"])
    return m.outputs["Mesh"]


def impact_events(t, slots, seed, side, centre, period, drop_r):
    """t.geometry becomes `slots` ground crowns (z = 0), stateless: slot j's event k = floor((t + phase_j) / P)
    seeds its position (Random Value ID = j + k * slots); a crown spreads and flattens over its life."""
    pts = t.node("GeometryNodePoints")
    pts.inputs["Count"].default_value = int(slots)
    t.geometry = _vertices(t, pts.outputs["Points"])
    j = index(t)
    phase = random(t, "FLOAT", 0.0, period, seed + 1)
    since = t.math("ADD", t.time(), phase)
    k = t.math("FLOOR", t.math("DIVIDE", since, period))
    age = t.math("DIVIDE", t.math("SUBTRACT", since, t.math("MULTIPLY", k, period)), period)   # [0, 1)
    ident = t.math("ADD", j, t.math("MULTIPLY", k, float(slots)))
    rx = random(t, "FLOAT", -side / 2.0, side / 2.0, seed + 2, ident)
    ry = random(t, "FLOAT", -side / 2.0, side / 2.0, seed + 3, ident)
    t.set_position(t.vec(t.math("ADD", centre[0], rx), t.math("ADD", centre[1], ry), 0.0))
    t.store("valora_age", age)
    spread = t.math("MULTIPLY", drop_r, t.math("ADD", 2.0, t.math("MULTIPLY", age, 10.0)))
    tall = t.math("MULTIPLY", drop_r * 0.8, t.math("SUBTRACT", 1.0, age))
    return t.vec(spread, spread, tall)


def water(name, glow=0.0):
    """Clear water: transmission 1, IOR 1.333, roughness 0.02 (render-studio's airborne water)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Base Color"].default_value = (0.94, 0.98, 1.0, 1.0)
    sh.inputs["Roughness"].default_value = 0.02
    sh.inputs["Transmission Weight"].default_value = 1.0
    sh.inputs["IOR"].default_value = 1.333
    if glow:
        sh.inputs["Emission Color"].default_value = (0.85, 0.92, 1.0, 1.0)
        sh.inputs["Emission Strength"].default_value = glow
    return m


def weather_object(scene, name, block):
    """An empty mesh object at the world origin (GN positions are world positions), tagged for probes."""
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob["valora_block"] = block
    return ob
