"""Per-vertex mesh-island ids via a temporary Geometry Nodes modifier (runs inside Blender).

Ingest (island summaries, the island of every surface sample) and the compiler (wheel tags) use the same
helper, so both see the same pieces. Blender numbers islands deterministically for a given mesh."""
import bpy

ATTR = "valora_island"
_GROUP = "valora_island_ids"
MOD = "valora_islands"
WELD_DIST = 1e-6  # object units; glTF split copies are bit-identical


def _group():
    """Island id per vertex, counted on a WELDED copy: glTF import splits vertices at every hard edge
    and UV seam, so a flat-shaded cube arrives as six islands. Weld (Merge by Distance, WELD_DIST in
    object units), take Mesh Island there, and read it back per original vertex through Sample Nearest
    (the welded vertex sits exactly where its copies were). Topology is unchanged."""
    ng = bpy.data.node_groups.get(_GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(_GROUP, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    weld = ng.nodes.new("GeometryNodeMergeByDistance")
    weld.inputs["Distance"].default_value = WELD_DIST
    near = ng.nodes.new("GeometryNodeSampleNearest")
    near.domain = "POINT"
    pos = ng.nodes.new("GeometryNodeInputPosition")
    isl = ng.nodes.new("GeometryNodeInputMeshIsland")
    pick = ng.nodes.new("GeometryNodeSampleIndex")
    pick.data_type, pick.domain = "INT", "POINT"
    st = ng.nodes.new("GeometryNodeStoreNamedAttribute")
    st.data_type, st.domain = "INT", "POINT"
    st.inputs["Name"].default_value = ATTR
    ng.links.new(gi.outputs[0], weld.inputs["Geometry"])
    ng.links.new(weld.outputs["Geometry"], near.inputs["Geometry"])
    ng.links.new(pos.outputs["Position"], near.inputs["Sample Position"])
    ng.links.new(weld.outputs["Geometry"], pick.inputs["Geometry"])
    ng.links.new(isl.outputs["Island Index"], pick.inputs["Value"])
    ng.links.new(near.outputs["Index"], pick.inputs["Index"])
    ng.links.new(gi.outputs[0], st.inputs["Geometry"])
    ng.links.new(pick.outputs["Value"], st.inputs["Value"])
    ng.links.new(st.outputs[0], go.inputs[0])
    return ng


def add_island_modifier(obj):
    mod = obj.modifiers.new(MOD, "NODES")
    mod.node_group = _group()
    return mod


def island_array(mesh):
    """int32 island id per vertex of an evaluated mesh that went through add_island_modifier, else None."""
    import numpy as np
    a = mesh.attributes.get(ATTR)
    if a is None or a.domain != "POINT":
        return None
    out = np.empty(len(mesh.vertices), dtype=np.int32)
    a.data.foreach_get("value", out)
    return out


def vertex_islands(obj):
    """Island id per ORIGINAL vertex of obj, or None when evaluation changed the vertex count."""
    mod = add_island_modifier(obj)
    try:
        bpy.context.view_layer.update()
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        try:
            arr = island_array(me)
            return arr if arr is not None and len(arr) == len(obj.data.vertices) else None
        finally:
            ev.to_mesh_clear()
    finally:
        obj.modifiers.remove(mod)


def summaries(co, isl, obj_index, min_n=8):
    """[{obj, id, n, lo, hi, centroid}] per island with >= min_n vertices. co: (n, 3) points."""
    import numpy as np
    if isl is None or not len(isl):
        return []
    n = np.bincount(isl)
    lo = np.full((len(n), 3), np.inf)
    hi = np.full((len(n), 3), -np.inf)
    np.minimum.at(lo, isl, co)
    np.maximum.at(hi, isl, co)
    sums = np.stack([np.bincount(isl, weights=co[:, k], minlength=len(n)) for k in range(3)], 1)
    return [{"obj": int(obj_index), "id": int(i), "n": int(n[i]), "lo": lo[i].tolist(), "hi": hi[i].tolist(),
             "centroid": (sums[i] / n[i]).tolist()} for i in np.nonzero(n >= min_n)[0]]
