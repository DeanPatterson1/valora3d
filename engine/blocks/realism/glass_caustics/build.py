"""Shadow caustics (TAXONOMY LM-01; METHODS §2.10 M-MNEE): Cycles' manifold next-event estimation, enabled
on the glass objects (casters), the floor (receivers) and every light. Refractive only, only inside
shadows, <= 4 refractive bounces, and it needs smooth normals: faceted glass gives noisy caustics
(materials are left alone, spec §4.5, so a faceted upload keeps its noise; noted, not fixed).
A linked Transmission Weight (a texture) counts as glass here (ingest resolved it to a mean > 0.5 or it
would not have reached the 5% share); a false positive only costs render time on that object."""
GLASS_TRANSMISSION = 0.5   # engine/ingest/measure.material_class: transmission > 0.5 is glass


def _is_glass(mat):
    if mat is None or not mat.use_nodes:
        return False
    n = next((x for x in mat.node_tree.nodes if x.type == "BSDF_PRINCIPLED"), None)
    s = n.inputs.get("Transmission Weight") if n is not None else None
    return s is not None and (s.is_linked or s.default_value > GLASS_TRANSMISSION)


def build(ctx):
    from engine.blender.realism_rig import ground_objects, record
    casters = [o for o in ctx.meshes if any(_is_glass(s.material) for s in o.material_slots)]
    for o in casters:
        o.cycles.is_caustics_caster = True
    receivers = ground_objects()
    for o in receivers:
        o.cycles.is_caustics_receiver = True
    lights = [o for o in ctx.scene.objects if o.type == "LIGHT"]
    for o in lights:
        o.data.cycles.is_caustics_light = True
    record("caustic_casters", len(casters))
    record("caustic_receivers", len(receivers))
    record("caustic_lights", len(lights))
