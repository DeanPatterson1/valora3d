"""plinth_spin's prop: a low cylinder the subject stands on (the turn itself is keyed from path.py). Radius
PLINTH_R x the footprint diagonal, height PLINTH_H x longest, centred under the subject's ground-centre pivot.
Material: in the studio a satin tone-matched to the cyc floor (a step up from the same paper), elsewhere
stone. It is tagged as ground (valora_ground), so contact_ground darkens its top under the subject, and the
resolver treats the plinth as a hard floor (no sink: applies standsOn). It does not turn: the subject turns
on it."""
import math

STONE = (0.42, 0.40, 0.37)       # (eng) outdoor plinth colour
SATIN_ROUGH, STONE_ROUGH = 0.35, 0.75
SIDES = 64


def _floor_colour(bpy):
    from engine.blender.realism_rig import ground_objects
    for ob in ground_objects():
        for m in ob.data.materials:
            sh = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m and m.use_nodes else None
            if sh is not None and not sh.inputs["Base Color"].is_linked:
                return tuple(sh.inputs["Base Color"].default_value)[:3]
    return None


def build(ctx):
    import bpy
    mod = ctx.catalog.motion_module("plinth_spin")                 # the same sizes the pose function uses
    prof = ctx.profile
    r, h = mod.plinth_radius(prof), mod.plinth_height(prof)
    verts = [(r * math.cos(2 * math.pi * k / SIDES), r * math.sin(2 * math.pi * k / SIDES), z)
             for z in (0.0, h) for k in range(SIDES)]
    faces = [[k, (k + 1) % SIDES, SIDES + (k + 1) % SIDES, SIDES + k] for k in range(SIDES)]
    faces += [list(range(SIDES))[::-1], list(range(SIDES, 2 * SIDES))]
    me = bpy.data.meshes.new("valora_plinth")
    me.from_pydata(verts, [], faces)
    for poly in me.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    ob = bpy.data.objects.new("valora_plinth", me)
    ob["valora_block"] = "motion/plinth_spin"
    ob["valora_ground"] = True
    ob.location = (prof.center[0], prof.center[1], 0.0)
    ctx.scene.collection.objects.link(ob)
    studio = ctx.script["world"]["id"] == "studio_cyc"
    floor = _floor_colour(bpy) if studio else None
    m = bpy.data.materials.new("valora_plinth")
    m.use_nodes = True
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    colour = tuple(0.85 * c for c in floor) if floor else STONE
    sh.inputs["Base Color"].default_value = (*colour, 1.0)
    sh.inputs["Roughness"].default_value = SATIN_ROUGH if floor else STONE_ROUGH
    me.materials.append(m)
    ctx.scene["valora_fx_plinth"] = {"radiusM": r, "heightM": h, "material": "satin" if floor else "stone"}
    return ob
