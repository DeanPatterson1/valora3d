"""Render settings per tier, eval passes and the render loop. Device selection ported from
product-render setup_cycles (tools/product-render/render_product.py:476).

Pass output (Blender 5.0, probed 2026-09-24): the File Output node takes
`file_output_items.new(socket_type, name)`, a `directory`, a `file_name` prefix and a node-level
`format`; each item can `override_node_format`. Per-pass PNGs work, so the EXR fallback is unused."""
import json
import os
import time
from pathlib import Path

import bpy

from engine.compiler.tiers import TIERS, cycles_recipe

DEVICE_ORDER = {"OPTIX": ["OPTIX", "CUDA"], "CUDA": ["CUDA", "OPTIX"], "CPU": []}
PASS_INDEX = 1  # subject objects (grade.SUBJECT_PASS_INDEX) and gloss materials


def setup_cycles(scene, tier):
    t = TIERS[tier]
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    prefs = bpy.context.preferences.addons["cycles"].preferences
    chosen = "CPU"
    for dt in DEVICE_ORDER.get(os.environ.get("VALORA_DEVICE", "OPTIX").upper(), ["OPTIX", "CUDA"]):
        try:
            prefs.compute_device_type = dt
            prefs.get_devices()
        except Exception:  # noqa: BLE001 - device type absent on this machine
            continue
        if any(d.type == dt for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == dt
            chosen = dt
            break
    cy.device = "GPU" if chosen != "CPU" else "CPU"
    cy.use_adaptive_sampling = True
    cy.use_denoising = t["denoise"]
    for k, v in cycles_recipe(tier).items():      # the whole pinned recipe (tiers.cycles_recipe)
        setattr(cy, k, v)
    if scene.compositing_node_group is None:    # grade skipped: the metering still exposes the frame
        scene.view_settings.exposure = float(scene.get("valora_meter_ev", 0.0))
    # VALORA_PERSISTENT=0 re-syncs every frame instead of updating the kept render data (hero pass 2026-09-28: a
    # motion job with ~100k per-frame spray streaks rendered its first frame in 86-116 s and every later frame in
    # 11+ min with persistent data on)
    scene.render.use_persistent_data = os.environ.get("VALORA_PERSISTENT", "1") != "0"
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    return chosen


def gloss_pass_indices(meshes):
    """Material pass_index 1 = TIERS 'gloss' (metallic >= 0.5 or roughness <= 0.3), measured with
    the same socket reader ingest uses."""
    from engine.ingest.blender_extract import _props
    from engine.ingest.measure import is_gloss
    for o in meshes:
        for slot in o.material_slots:
            if slot.material is not None:
                slot.material.pass_index = PASS_INDEX if is_gloss(_props(slot.material)) else 0


def _grade_tree(scene):
    """The grade's compositor tree, or a pass-through one when the grade was skipped."""
    tree = scene.compositing_node_group
    if tree is not None:
        return tree, next(n for n in tree.nodes if n.type == "R_LAYERS")
    tree = bpy.data.node_groups.new("valora_passthrough", "CompositorNodeTree")
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = tree
    src = tree.nodes.new("CompositorNodeRLayers")
    src.scene = scene
    tree.links.new(src.outputs["Image"], tree.nodes.new("NodeGroupOutput").inputs["Image"])
    return tree, src


def _file_output(tree, directory, sources):
    """One File Output node writing <directory>/<name>_<frame:04d>.png per source. Masks are 8-bit BW,
    mist 16-bit BW. Data values: never view-transformed."""
    fo = tree.nodes.new("CompositorNodeOutputFile")
    fo.name = "valora_passes"
    fo.directory = str(directory) + os.sep
    fo.file_name = ""
    fo.save_as_render = False
    fo.format.media_type = "IMAGE"  # 5.0 default is MULTI_LAYER_IMAGE (EXR only)
    fo.format.file_format, fo.format.color_mode, fo.format.color_depth = "PNG", "BW", "8"
    for i, (name, (socket, depth)) in enumerate(sources.items()):
        # 5.0 path = directory + file_name + item name; '#' in the item name becomes the frame.
        item = fo.file_output_items.new("FLOAT", f"{name}_####")
        item.save_as_render = False
        if depth != "8":
            item.override_node_format = True
            item.format.media_type = "IMAGE"
            item.format.file_format, item.format.color_mode, item.format.color_depth = "PNG", "BW", depth
        tree.links.new(socket, fo.inputs[i])
    return fo


def add_passes(scene, out_dir, far_m):
    """Subject mask, gloss mask and mist written per frame by a File Output node in the grade tree."""
    vl = scene.view_layers[0]
    vl.use_pass_object_index = vl.use_pass_material_index = vl.use_pass_mist = True
    if scene.world is None:  # world block skipped: mist settings still live on a World
        scene.world = bpy.data.worlds.new("valora_world")
    scene.world.mist_settings.start, scene.world.mist_settings.depth = 0.0, far_m
    scene.world.mist_settings.falloff = "LINEAR"
    tree, src = _grade_tree(scene)
    masks = {}
    for name, pass_name in (("mask", "Object Index"), ("gloss", "Material Index")):
        idm = tree.nodes.new("CompositorNodeIDMask")
        idm.name = f"valora_{name}_id"
        idm.inputs["Index"].default_value = PASS_INDEX
        tree.links.new(src.outputs[pass_name], idm.inputs["ID value"])
        masks[name] = (idm.outputs["Alpha"], "8")
    masks["mist"] = (src.outputs["Mist"], "16")
    return _file_output(tree, Path(out_dir) / "passes", masks)


def grain_png(path, amount, seed, frame):
    """Sensor grain on the written 8-bit frame, after AgX (engine/film_grain.py, render-studio's delivery grain)."""
    import numpy as np
    from engine.film_grain import apply_grain
    img = bpy.data.images.load(str(path), check_existing=False)
    try:
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        px[..., :3] = apply_grain(px[..., :3], amount, seed, frame)
        px[..., :3] = np.round(px[..., :3] * 255.0) / 255.0
        img.pixels.foreach_set(px.ravel())
        img.filepath_raw, img.file_format = str(path), "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


def render_frames(scene, frames, out_dir, tier, device, samples_by_frame=None):
    out = Path(out_dir)
    (out / "beauty").mkdir(parents=True, exist_ok=True)
    log = {"blender": bpy.app.version_string, "device": device, "tier": tier, "samples": TIERS[tier]["samples"],
           "resolution": [scene.render.resolution_x, scene.render.resolution_y], "frames": []}
    t_all = time.perf_counter()
    if frames == "all":  # one still per frame: the log is the harness's frame list, so it lists every frame
        frames = range(scene.frame_start, scene.frame_end + 1)
    for f in frames:
        scene.frame_set(f)
        scene.render.filepath = str(out / "beauty" / f"{f:04d}.png")
        n = (samples_by_frame or {}).get(f, TIERS[tier]["samples"])
        if samples_by_frame:
            scene.cycles.samples = n              # a close detail's budget (tiers.frame_samples)
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        grain = scene.get("valora_grain")
        if grain is not None and os.environ.get("VALORA_KEEP_CLEAN"):   # the grain-0 benchmark plate, beside
            import shutil
            (out / "clean").mkdir(exist_ok=True)
            shutil.copyfile(scene.render.filepath, out / "clean" / f"{f:04d}.png")
        if grain is not None:
            grain_png(scene.render.filepath, float(grain["amount"]), int(grain["seed"]), f)
        rec = {"frame": f, "seconds": round(time.perf_counter() - t0, 3)}
        if n != TIERS[tier]["samples"]:
            rec["samples"] = n
        log["frames"].append(rec)
    log["totalSeconds"] = round(time.perf_counter() - t_all, 3)
    (out / "render_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log
