"""Contact shadow + occlusion and ground sink (TAXONOMY CD-01, CD-10; METHODS §2.1 CD-01).

Cycles already casts the subject's shadow on the floor. This adds ray-traced contact occlusion to every
ground material (valora_ground): the Ambient Occlusion shader node darkens the floor where the subject is
within its reach (engine/physics/contact.contact_reach: 5% of its height, or 1.5 x a vehicle's ride height
so the seam reaches under the sills), giving the tight dark seam that separates grounded from pasted
(TIERS T1-X2). It also lowers the subject into soft ground by sinkMm through the realism offset.
No decal: a decal is only for worlds without a floor (METHODS CD-01)."""
from engine.physics import contact

CREASE_POW = 2.0   # (eng) look-check real_rw_*: only the closing gap darkens, Cycles casts the shadow


def build(ctx):
    import bpy
    from engine.blender.realism_rig import ground_objects, record, rig
    p = ctx.params
    _, offset = rig()
    sink = p["sinkMm"] / 1000.0
    offset.location.z -= sink
    dist = contact.contact_reach(ctx.profile.sizeM[2], (ctx.profile.vehicle or {}).get("rideHeightM"))
    done = set()
    for ob in ground_objects():
        for slot in ob.material_slots:
            mat = slot.material
            if mat is None or mat.name in done or not mat.use_nodes:
                continue
            nt = mat.node_tree
            bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is None:
                continue
            done.add(mat.name)
            base = bsdf.inputs["Base Color"]
            ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao.name, ao.only_local, ao.samples = "valora_contact_ao", False, 16
            ao.inputs["Distance"].default_value = dist
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            # ShaderNodeMix has float, vector and colour sockets with the same names; name lookup returns
            # the (hidden) float ones, so pick the colour sockets by identifier.
            sock = lambda coll, ident: next(x for x in coll if x.identifier == ident)
            fac, a, b = sock(mix.inputs, "Factor_Float"), sock(mix.inputs, "A_Color"), sock(mix.inputs, "B_Color")
            # Cycles already occludes the floor's lighting under the subject, so a plain albedo x AO darkened
            # that shadow twice (realism audit: at the default 0.8 the whole underbody patch went near black).
            # The seam is the crease only: the factor follows (1 - ao)^CREASE_POW, ~0.2 at ao 0.5, the full
            # `occlusion` only where the gap closes (tyre contact, a base sitting on the floor).
            miss = nt.nodes.new("ShaderNodeMath")
            miss.operation = "SUBTRACT"
            miss.inputs[0].default_value = 1.0
            nt.links.new(ao.outputs["AO"], miss.inputs[1])
            crease = nt.nodes.new("ShaderNodeMath")
            crease.operation = "POWER"
            crease.inputs[1].default_value = CREASE_POW
            nt.links.new(miss.outputs[0], crease.inputs[0])
            weight = nt.nodes.new("ShaderNodeMath")
            weight.operation = "MULTIPLY"
            weight.inputs[1].default_value = p["occlusion"]
            nt.links.new(crease.outputs[0], weight.inputs[0])
            nt.links.new(weight.outputs[0], fac)
            b.default_value = (0.0, 0.0, 0.0, 1.0)                     # toward black, by the crease weight
            if base.is_linked:
                src = base.links[0].from_socket
                nt.links.new(src, ao.inputs["Color"])
                nt.links.new(src, a)
            else:
                ao.inputs["Color"].default_value = base.default_value
                a.default_value = base.default_value
            nt.links.new(sock(mix.outputs, "Result_Color"), base)
    record("sink_m", sink)
    record("contact_ao_materials", len(done))
    record("contact_ao_links_ok", all(l.is_valid for n in done for l in bpy.data.materials[n].node_tree.links))
    record("contact_ao_distance_m", dist)
