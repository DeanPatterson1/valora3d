"""Shared stateless weather Geometry Nodes (plan Task 64). Runs inside Blender only.

Everything here is a function of (scene time, seed, params, the camera and subject transforms): no
simulation zone, no bake, no frame that depends on the one before (METHODS R1), so preview equals final and
any frame range renders anywhere.

box_points: N seeded points on a world-fixed lattice, advanced analytically by a drift field and wrapped into
a square box that follows the active camera (Scene Time x velocity, Wrap per axis). A point stays still in
the world between wraps, so it streaks from its own velocity, and a wrap only happens at a box face, far
from the view. shelter: deletes points inside the posed subject's footprint column below its top (Object
Info on valora_realism_offset, so shelter follows a moving subject) and points too close to the camera.
lattice_impacts: ground crowns on the shared impact lattice (engine/physics/rain.impact_lattice), the same
Voronoi the wet_surface ripples read, so every frame evaluates on its own and crowns and ripples agree.

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


GUST_FD_S = 0.005    # the central-difference step of the gust term's time derivative (s; review chunk5 #9)


def gusts(t, mean, per_ms, carrier):
    """The shared wind field (valora_wind, engine/blender/wind_field) at every point, scaled by the consumer's
    perMs, applied statelessly (review chunk3 #4): each point moves by (local wind - mean) x GUST_RESPONSE_S on
    top of its mean drift. Gustiness and turbulence therefore reach rain and snow exactly as they reach foliage.

    Stores the point's `velocity` = d(position)/dt of that same trajectory (review chunk5 #9): the carrier (the
    drift's derivative, a vector socket) + GUST_RESPONSE_S x dW/dt along the point's path. The field is
    W(p, t) = F(p - a t) (wind_field: gusts and eddies advect at the mean wind a = mean / perMs), so along a point
    moving at the carrier c, W(p + c h, t + h) = W(p + (c - a) h, t): the total derivative is a central difference
    in position alone, with the same group. Without the group (no wind block) nothing moves and the velocity is the
    carrier."""
    from engine.physics.wind import GUST_RESPONSE_S
    ng = bpy.data.node_groups.get("valora_wind")
    if ng is None or per_ms == 0.0:
        store_vector(t, "velocity", carrier)
        return
    h = GUST_FD_S
    wind = lambda p: t.vmath("SCALE", t.group(ng, Position=p).outputs["Wind"], scale=per_ms)  # noqa: E731
    rel = t.vmath("SUBTRACT", carrier, t.vec(*(m / per_ms for m in mean)))                  # c - a
    ahead = wind(t.vmath("ADD", t.position(), t.vmath("SCALE", rel, scale=h)))
    behind = wind(t.vmath("SUBTRACT", t.position(), t.vmath("SCALE", rel, scale=h)))
    dwdt = t.vmath("SCALE", t.vmath("SUBTRACT", ahead, behind), scale=1.0 / (2.0 * h))
    store_vector(t, "velocity", t.vmath("ADD", carrier, t.vmath("SCALE", dwdt, scale=GUST_RESPONSE_S)))  # before the move
    dev = t.vmath("SUBTRACT", wind(t.position()), t.vec(*mean))
    t.set_position(t.vmath("ADD", t.position(), t.vmath("SCALE", dev, scale=GUST_RESPONSE_S)))


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


def lattice_impacts(t, lat, centre, drop_r):
    """t.geometry becomes the ground crowns of the shared impact lattice (engine/physics/rain.impact_lattice;
    review chunk3 #6): one sample per lattice cell around `centre` (x, y sockets, world-fixed cells), placed on
    its cell's Voronoi feature point, with age = frac(t / period + the cell's Voronoi red) as a share of the
    crown's life, deleted when that age is past the life. The wet_surface ripple shader builds the same Voronoi,
    so every crown sits on a ripple's centre with the same age. Returns the crown scale vector."""
    S, P, J, n = lat["cellM"], lat["periodS"], lat["jitter"], int(lat["across"])
    ox, oy = lat["offset"]
    pts = t.node("GeometryNodePoints")
    pts.inputs["Count"].default_value = n * n
    t.geometry = _vertices(t, pts.outputs["Points"])
    j = index(t)
    ix, iy = t.math("MODULO", j, float(n)), t.math("FLOOR", t.math("DIVIDE", j, float(n)))
    base = lambda c, o: t.math("SUBTRACT", t.math("FLOOR", t.math("ADD", t.math("DIVIDE", c, S), o)), n // 2)  # noqa: E731
    cx, cy = centre
    sx = t.math("ADD", t.math("ADD", base(cx, ox), ix), J / 2.0)      # the middle of the cell's jitter square
    sy = t.math("ADD", t.math("ADD", base(cy, oy), iy), J / 2.0)
    vor = t.node("ShaderNodeTexVoronoi", voronoi_dimensions="2D", feature="F1", distance="EUCLIDEAN")
    vor.inputs["Scale"].default_value, vor.inputs["Randomness"].default_value = 1.0, J
    t.feed(vor.inputs["Vector"], t.vec(sx, sy, 0.0))
    fx, fy, _ = t.xyz(vor.outputs["Position"])
    red = t.xyz(vor.outputs["Color"])[0]
    age = t.math("FRACT", t.math("ADD", t.math("DIVIDE", t.time(), P), red))
    life = t.math("DIVIDE", t.math("MULTIPLY", age, P), lat["lifeS"])          # 0..1 over the crown's life
    t.set_position(t.vec(t.math("MULTIPLY", t.math("SUBTRACT", fx, ox), S), t.math("MULTIPLY", t.math("SUBTRACT", fy, oy), S), 0.0))
    t.store("valora_age", life)
    t.store("valora_red", red)
    gone = t.node("GeometryNodeDeleteGeometry")
    t.feed(gone.inputs["Geometry"], t.geometry)
    t.feed(gone.inputs["Selection"], t.math("GREATER_THAN", life, 1.0))
    t.geometry = gone.outputs["Geometry"]
    # the scale is evaluated where it is consumed (instancing, after these and the shelter's deletions compact
    # the indices): read the age captured on each point, never the index-derived field (review chunk5 #8)
    kept = t.attr("valora_age")
    spread = t.math("MULTIPLY", drop_r, t.math("ADD", 2.0, t.math("MULTIPLY", kept, 10.0)))
    tall = t.math("MULTIPLY", drop_r * 0.8, t.math("MAXIMUM", t.math("SUBTRACT", 1.0, kept), 0.0))
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
