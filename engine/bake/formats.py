"""The Blender 5.0.1 simulation cache facts the bake stage relies on: one portable format per method.

Every fact below was measured by engine/tests/test_sim_api_probe_blender.py on 2026-09-28 (Blender
5.0.1, build 2025-12-16); its numbers are recorded in var/probe/sim_api.json. No format keeps Blender's
own blendcache_* folders (they are tied to a saved .blend path). Constants and pure stdlib helpers
only: this module is imported by the host and inside Blender.

rigid_keys (test_bullet_frame_set_is_deterministic_and_rests_on_the_plane)
    Bullet is stepped with scene.frame_set from rigidbody_world.point_cache.frame_start. Per-piece
    matrix_world is bit-identical across two runs in one process and across two Blender processes, so
    the bake writes per-piece transforms (JSON) that build() keys as keyframes: any frame, any order.
    Pieces set rigid_body.use_margin=True and collision_margin=0: with 60 substeps and 20 iterations
    both that and the default convex-hull margin (0.04) rest a 0.1 m cube at 0.050 m (probe: 0.05000
    vs 0.05003), but at Blender's default 10 substeps the default margin rested it 1-4 mm high and
    still jittering at frame 120 (manual probe, same day), while margin 0 rested exactly.
    bpy.ops.rigidbody.bake_to_keyframes does NOT work headless (its inner anim.keyframe_insert_by_name
    poll fails even under temp_override), so there is no operator fallback: keys come from the JSON.
cloth_pc2 (test_cloth_pc2_round_trips_through_mesh_cache_with_an_offset)
    Legacy cloth stepped with frame_set; the evaluated local vertices written to PC2 (the 32-byte header,
    then little-endian float32 xyz per vertex per sample) round-trip through a MESH_CACHE modifier
    (cache_format 'PC2') with 0 error. Offset: sample i plays at scene frame modifier.frame_start + i
    (default frame_start 0.0); the PC2 header's start frame is ignored in time_mode 'FRAME'. Motion
    blur: Cycles' object use_deform_motion exists for the modifier-deformed mesh (not render-verified).
gn_disk (test_gn_sim_zone_bakes_to_disk_and_a_fresh_scene_reads_it_out_of_order)
    NodesModifier.bakes[i] with bake_target 'DISK', use_custom_path + directory and a custom frame range,
    baked by bpy.ops.object.geometry_node_bake_single(session_uid, modifier_name, bake_id) under
    temp_override(object, active_object). Layout: meta/<frame:05d>_<sub:05d>.json + blobs/. A fresh
    process with the same (even an edited) tree and the directory reads frames out of order with no
    re-simulation. There is NO frame-offset API: frames are absolute scene frames, and a reader range
    of 101..160 over a 1..60 bake holds frame 60. So a GN sim bakes on the render scene's own frame
    numbers and its pre-roll runs before the clip start; negative frames work (-11..48 baked and read
    back exactly; files named -0011_00000.json).
gas_vdb (test_gas_bakes_vdb_and_a_volume_plays_it_with_a_frame_offset)
    Mantaflow GAS with cache_type 'ALL', cache_data_format 'OPENVDB' and bpy.ops.fluid.bake_all() under
    temp_override(object=domain, active_object=domain, scene) writes data/fluid_data_####.vdb with the
    grids density, flame, shadow, temperature and velocity (VECTOR_FLOAT). A Volume object plays the
    sequence: file index = scene_frame - Volume.frame_start + 1 + Volume.frame_offset, and
    sequence_mode 'CLIP' is empty outside the range. Velocity defaults: velocity_grid 'velocity',
    velocity_scale 1.0, velocity_unit 'FRAME' (enum SECOND, FRAME).
liquid_abc (test_liquid_speed_vectors_need_uni_data_and_survive_alembic_with_an_offset)
    Mantaflow LIQUID with use_mesh and use_speed_vectors. FAILED PATH: with cache_data_format 'OPENVDB'
    (the default) 5.0.1 silently drops the mesh speed vectors (no lVelMesh files; the 'velocity'
    attribute is all zero). With cache_data_format 'UNI' they are written (mesh/lVelMesh_####.uni) and
    the evaluated domain mesh carries a non-zero POINT 'velocity'. bpy.ops.wm.alembic_export(selected=
    True, evaluation_mode='RENDER') of the domain keeps that attribute exactly; the exporter reads the
    real selection flags, not temp_override, so the domain must really be selected. Import gives a
    MESH_SEQUENCE_CACHE whose evaluated mesh has attribute 'velocity' (CacheFile.velocity_name
    '.velocities' is not the path used). Offset: abc frame = scene_frame - CacheFile.frame_offset. The
    raw velocity magnitude (max about 11 at res 32 for a drop under 0.7 m) is not m/s: its unit is
    calibrated in T114 before motion blur trusts it.

Force fields (test_wind_seed_clamps_to_1_128_and_strength_is_a_force): field.seed is clamped to 1..128
(200 -> 128, 0 -> 1), never rejected. A WIND field with flow 0 is a constant force on a legacy
particle: a = strength / mass m/s^2, so the drift over 1 s = strength / (2 mass) m (T107's input).
"""
import struct

PROBED = "5.0.1 2026-09-28"

FORMATS = {
    "rigid_keys": {
        "cache": "bake.json: per-piece matrix_world per frame -> keyframes in build()",
        "offset_mode": "keys are written at render frames: bake frame b -> render frame b - preroll",
        "velocity": "from the keyframes (object motion blur)",
        "operator_override": None,                     # stepped with scene.frame_set, no operator
        "piece_margin": {"use_margin": True, "collision_margin": 0.0},
        "fallback": None,                              # bake_to_keyframes fails headless
        "probed": PROBED,
    },
    "cloth_pc2": {
        "cache": "PC2 point cache -> MESH_CACHE modifier (cache_format 'PC2')",
        "offset_mode": "modifier.frame_start = render frame of sample 0 (sample i at frame_start + i)",
        "velocity": "deformation motion blur (Cycles object use_deform_motion)",
        "operator_override": None,                     # stepped with scene.frame_set
        "probed": PROBED,
    },
    "gn_disk": {
        "cache": "NodesModifier bake directory (bake_target 'DISK')",
        "offset_mode": "none: bake on absolute render frames, pre-roll before the clip (negative frames ok)",
        "velocity": "a stored 'velocity' point attribute",
        "operator_override": "object.geometry_node_bake_single(session_uid, modifier_name, bake_id) "
                             "under temp_override(object, active_object)",
        "probed": PROBED,
    },
    "gas_vdb": {
        "cache": "OpenVDB sequence data/fluid_data_####.vdb -> Volume object (is_sequence, CLIP)",
        "offset_mode": "Volume.frame_start = render frame of file 0001; Volume.frame_offset shifts the file",
        "velocity": {"grid": "velocity", "unit": "FRAME", "scale": 1.0},
        "operator_override": "fluid.bake_all() under temp_override(object=domain, active_object=domain, scene)",
        "cache_data_format": "OPENVDB",
        "probed": PROBED,
    },
    "liquid_abc": {
        "cache": "Alembic of the evaluated domain mesh -> MESH_SEQUENCE_CACHE",
        "offset_mode": "CacheFile.frame_offset = render frame - bake frame",
        "velocity": {"attribute": "velocity", "domain": "POINT", "unit": "uncalibrated (T114)"},
        "operator_override": "fluid.bake_all() under temp_override(object=domain, active_object=domain, "
                             "scene); wm.alembic_export(selected=True) with the domain really selected",
        "cache_data_format": "UNI",                    # OPENVDB drops mesh speed vectors in 5.0.1
        "probed": PROBED,
    },
}

_PC2_HEADER = struct.Struct("<12siiffi")               # 32 bytes


def pc2_header(n_verts, start, rate, n_samples):
    """The 32-byte PC2 header: signature, version 1, point count, start frame, sample rate, samples."""
    return _PC2_HEADER.pack(b"POINTCACHE2\0", 1, int(n_verts), float(start), float(rate), int(n_samples))


def pc2_frame_bytes(verts):
    """One PC2 sample: little-endian float32 x, y, z per vertex, in vertex order."""
    flat = [float(c) for v in verts for c in v]
    return struct.pack(f"<{len(flat)}f", *flat)
