"""Shadow caustics (TAXONOMY LM-01; METHODS §2.10 M-MNEE): Cycles' manifold next-event estimation, enabled
on the glass objects (casters), the floor (receivers) and every light. Refractive only, only inside
shadows, <= 4 refractive bounces, and it needs smooth normals: faceted glass gives noisy caustics
(materials are left alone, spec §4.5, so a faceted upload keeps its noise; noted, not fixed).
A linked Transmission Weight (a texture) counts as glass here (ingest resolved it to a mean > 0.5 or it
would not have reached the 5% share); a false positive only costs render time on that object.
Review item 9: MNEE works only toward light objects, so a scene lit by its world alone gets no flags at all;
and a caster's strength is its transmission x the luminance of its transmission (base) colour: a dark smoked
glass (< CAUSTIC_MIN) throws almost no caustic and is left out (a linked colour counts as clear)."""
GLASS_TRANSMISSION = 0.5   # engine/ingest/measure.material_class: transmission > 0.5 is glass
CAUSTIC_MIN = 0.2          # caster weight (transmission x colour luminance) below which it is skipped (eng)


def caustic_weight(mat):
    """0 for non-glass; else transmission (1 if textured) x luminance of the Base Color (1 if textured)."""
    if mat is None or not mat.use_nodes:
        return 0.0
    n = next((x for x in mat.node_tree.nodes if x.type == "BSDF_PRINCIPLED"), None)
    s = n.inputs.get("Transmission Weight") if n is not None else None
    if s is None or not (s.is_linked or s.default_value > GLASS_TRANSMISSION):
        return 0.0
    c = n.inputs.get("Base Color")
    lum = 1.0 if c is None or c.is_linked else (0.2126 * c.default_value[0] + 0.7152 * c.default_value[1]
                                                + 0.0722 * c.default_value[2])
    return (1.0 if s.is_linked else float(s.default_value)) * float(lum)


def build(ctx):
    from engine.blender.realism_rig import ground_objects, record
    lights = [o for o in ctx.scene.objects if o.type == "LIGHT"]
    weights = [max((caustic_weight(s.material) for s in o.material_slots), default=0.0) for o in ctx.meshes]
    casters = [o for o, w in zip(ctx.meshes, weights) if w >= CAUSTIC_MIN] if lights else []
    receivers = ground_objects() if casters else []
    for o in casters:
        o.cycles.is_caustics_caster = True
    for o in receivers:
        o.cycles.is_caustics_receiver = True
    for o in (lights if casters else []):
        o.data.cycles.is_caustics_light = True
    record("caustic_max_weight", max(weights, default=0.0))
    record("caustic_casters", len(casters))
    record("caustic_receivers", len(receivers))
    record("caustic_lights", len(lights) if casters else 0)
