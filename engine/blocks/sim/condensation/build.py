"""condensation: micro-droplets and a fogged film below the fill line (maths in engine/physics/condensation.py).

Two separate objects read the upload's evaluated meshes through Object Info (the upload gets no modifier and no
material change, so its bounds and look are untouched):
- valora_condensation_film: the meshes' faces that are below the fill line and not facing down, pushed FILM_M
  out along their normals, with a rough, faintly white water film (the fog). `fog` sets its strength (0: no
  film);
- valora_condensation_drops: points distributed on the same zone at density x 1e4 per m2 (capped at MAX_DROPS),
  each instancing a smooth water dome of a real 0.2-1.5 mm diameter (size_m: most small), flattened along the
  surface normal (a bead's cap is ~0.5 x its width) and sitting on the film.
Stateless: nothing moves, so nothing is baked (bake.method "none"); the few running drops come from the coupled
`runners` sim."""
FILM_ALPHA = 0.35          # the film's opacity at fog 1 (eng; the owner grades the look)
DOME_H = 0.35              # a bead's height / width: condensation wets a cold can, flat caps (eng)


def _meshes_geo(t, meshes):
    join = t.node("GeometryNodeJoinGeometry")
    for m in meshes:
        if m.type != "MESH":
            continue
        info = t.node("GeometryNodeObjectInfo", transform_space="RELATIVE")
        info.inputs["Object"].default_value = m
        t.ng.links.new(info.outputs["Geometry"], join.inputs[0])
    rm = t.node("GeometryNodeRemoveAttribute")
    t.feed(rm.inputs["Geometry"], join.outputs[0])
    rm.inputs["Name"].default_value = "custom_normal"
    return rm.outputs["Geometry"]


def _in_zone(t, C, fill_z):
    nz = t.xyz(t.node("GeometryNodeInputNormal").outputs[0])[2]
    pz = t.xyz(t.position())[2]
    return t.math("MULTIPLY", t.math("GREATER_THAN", nz, C.DOWN_NZ), t.math("LESS_THAN", pz, fill_z))


def _film_material(bpy, fog):
    m = bpy.data.materials.new("valora_condensation_fog")
    m.use_nodes = True
    nt = m.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Base Color"].default_value = (0.86, 0.89, 0.92, 1.0)   # frost-white micro-mist scatter
    sh.inputs["Roughness"].default_value = 0.4
    sh.inputs["Transmission Weight"].default_value = 0.85
    sh.inputs["IOR"].default_value = 1.333
    sh.inputs["Alpha"].default_value = max(0.0, min(1.0, FILM_ALPHA * fog))
    return m


def _dome(t, bpy):
    ico = t.node("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 0.5
    ico.inputs["Subdivisions"].default_value = 2
    sm = t.node("GeometryNodeSetShadeSmooth")
    t.feed(sm.inputs["Geometry"], ico.outputs["Mesh"])
    return sm.outputs[0]


def build(ctx):
    import bpy

    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.physics import condensation as C
    from engine.physics import sim_facts
    p, prof = ctx.params, ctx.profile
    fill_z = sim_facts.fill_line(prof, ctx.script.get("markers") or [])["z"]
    meshes = list(ctx.meshes)
    seed = int(ctx.seed) % 100000
    # the fog film
    if p["fog"] > 0:
        ob = wn.weather_object(ctx.scene, "valora_condensation_film", "sim/condensation")
        t = Tree("valora_condensation_film")
        t.geometry = _meshes_geo(t, meshes)
        dl = t.node("GeometryNodeDeleteGeometry", domain="FACE")
        t.feed(dl.inputs["Geometry"], t.geometry)
        t.feed(dl.inputs["Selection"], t.math("SUBTRACT", 1.0, _in_zone(t, C, fill_z)))
        t.geometry = dl.outputs[0]
        t.set_position(t.vmath("ADD", t.position(), t.vmath("SCALE", t.node("GeometryNodeInputNormal").outputs[0],
                                                             scale=C.FILM_M)))
        mat = t.node("GeometryNodeSetMaterial")
        t.feed(mat.inputs["Geometry"], t.geometry)
        mat.inputs["Material"].default_value = _film_material(bpy, float(p["fog"]))
        t.geometry = mat.outputs[0]
        add_modifier(ob, t.finish(), "valora_condensation_film")
    # the micro-droplets
    area = _zone_area(meshes, fill_z, C)
    ob = wn.weather_object(ctx.scene, "valora_condensation_drops", "sim/condensation")
    ob.visible_shadow = False      # without caustics a clear drop's shadow is a dark speck (it reads as dirt)
    t = Tree("valora_condensation_drops")
    dist = t.node("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM")
    t.feed(dist.inputs["Mesh"], _meshes_geo(t, meshes))
    t.feed(dist.inputs["Selection"], _in_zone(t, C, fill_z))
    dist.inputs["Density"].default_value = C.effective_per_m2(area, p["density"])
    dist.inputs["Seed"].default_value = seed
    t.geometry = dist.outputs["Points"]
    t.store("valora_n", dist.outputs["Normal"], "FLOAT_VECTOR")
    u = wn.random(t, "FLOAT", 0.0, 1.0, seed + 11)
    lo, hi = C.SIZE_MM
    d = t.math("MULTIPLY", t.math("ADD", lo, t.math("MULTIPLY", hi - lo, t.math("POWER", u, C.SIZE_SKEW))), 0.001)
    t.store("size", d)
    nrm = t.attr("valora_n", "FLOAT_VECTOR")
    # the dome's centre: on the film, lifted by a quarter of its height so the cap stands on the surface
    t.set_position(t.vmath("ADD", t.position(), t.vmath("SCALE", nrm, scale=t.math("ADD", C.FILM_M,
                                                                                  t.math("MULTIPLY", d, 0.25 * DOME_H)))))
    align = t.node("FunctionNodeAlignRotationToVector", axis="Z")
    t.feed(align.inputs["Vector"], nrm)
    inst = t.node("GeometryNodeInstanceOnPoints")
    t.feed(inst.inputs["Points"], t.geometry)
    t.feed(inst.inputs["Instance"], _dome(t, bpy))
    t.feed(inst.inputs["Rotation"], align.outputs[0])
    size = t.attr("size")
    t.feed(inst.inputs["Scale"], t.vec(size, size, t.math("MULTIPLY", size, DOME_H)))
    t.geometry = inst.outputs["Instances"]
    sm = t.node("GeometryNodeSetMaterial")
    t.feed(sm.inputs["Geometry"], t.geometry)
    from engine.blender.runners import water
    sm.inputs["Material"].default_value = water()
    t.geometry = sm.outputs[0]
    add_modifier(ob, t.finish(), "valora_condensation_drops")


def _zone_area(meshes, fill_z, C):
    """The zone's area in m2 (world), for the instance cap."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    area = 0.0
    for m in meshes:
        if m.type != "MESH":
            continue
        ev = m.evaluated_get(dg)
        me = ev.to_mesh()
        mw = m.matrix_world
        nm = mw.to_3x3().inverted_safe().transposed()
        for poly in me.polygons:
            c = mw @ poly.center
            n = (nm @ poly.normal).normalized()
            if C.in_zone(tuple(n), c.z, fill_z):
                vs = [mw @ me.vertices[i].co for i in poly.vertices]
                a = 0.0
                for i in range(1, len(vs) - 1):
                    a += 0.5 * (vs[i] - vs[0]).cross(vs[i + 1] - vs[0]).length
                area += a
        ev.to_mesh_clear()
    return area
