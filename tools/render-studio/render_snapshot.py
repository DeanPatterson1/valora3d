"""Blender entry point: render a faithfully exported build in a local studio.

blender -b --python render_snapshot.py -- /path/to/pipeline-job.json
The input GLB is sibling snapshot.glb. Known browser materials get conservative
offline equivalents; per-panel paint colors and the snapshot geometry survive.
"""
import json
import math
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_materials import calibrate_materials, add_water_beads
import film_camera
import rain_scene
import surface_detail
import component_materials
import rain_look
import rain_atmosphere
import road_weathering
import scene_plan_camera


def progress(**event):
    print("PROGRESS " + json.dumps(event), flush=True)


def material(name, color, roughness, metallic=0.0):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return result


def area_light(name, position, target, energy, size, color, size_y=None):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "RECTANGLE"
    data.size = size
    data.size_y = size_y if size_y else size
    light = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(light)
    light.location = position
    light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    return light


def pick_engine(scene, engine, samples):
    if engine in ("EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = "BLENDER_EEVEE_NEXT"
        except TypeError:
            scene.render.engine = "BLENDER_EEVEE"  # Blender 5 renamed it back.
        # Blender 4 and 5 expose EEVEE samples differently; keep its default if
        # this installed version has no explicit per-scene control.
        eevee = getattr(scene, "eevee", None)
        if eevee and hasattr(eevee, "taa_render_samples"):
            eevee.taa_render_samples = samples
        elif eevee and hasattr(eevee, "taa_samples"):
            eevee.taa_samples = samples
        return "EEVEE GPU"
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.render.use_persistent_data = True
    preferences = bpy.context.preferences.addons["cycles"].preferences
    for device_type in ("OPTIX", "CUDA", "HIP", "METAL"):
        try:
            preferences.compute_device_type = device_type
            preferences.get_devices()
            active = []
            for device in preferences.devices:
                device.use = device.type == device_type
                if device.use:
                    active.append(device.name)
            if active:
                scene.cycles.device = "GPU"
                return device_type + ": " + ", ".join(active)
        except (TypeError, ValueError, RuntimeError):
            continue
    scene.cycles.device = "CPU"
    return "CPU"


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) != 1:
        raise ValueError("Expected one job JSON path")
    spec_path = Path(args[0]).resolve()
    job_dir = spec_path.parent
    job = json.loads(spec_path.read_text(encoding="utf-8"))
    frames = job_dir / "frames"
    frames.mkdir(exist_ok=True)
    started = time.monotonic()
    progress(status="preparing", progress=0.01, frame=0)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(job_dir / "snapshot.glb"))
    bpy.context.view_layer.update()
    car_meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and not obj.hide_render]
    if not car_meshes:
        raise ValueError("The snapshot contains no visible car meshes")
    points = [obj.matrix_world @ Vector(corner) for obj in car_meshes for corner in obj.bound_box]
    if not all(math.isfinite(value) for point in points for value in point):
        raise ValueError("The snapshot has invalid geometry bounds")
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    center = (low + high) / 2
    extent = high - low
    span = max(extent)
    if span < 0.001 or span > 10000:
        raise ValueError("The snapshot size cannot be framed")
    scale = span / 4.8
    rainy = job.get('scene') == 'rainy_courtyard'
    # A spec'd job carries `look`; its grade / exposure / lamp switches apply to
    # every scene. Without one the orbit scenes keep their pre-spec literals.
    directed = rainy or job.get('look') is not None
    rain_look.configure(job.get('look'))
    # The 2026-09-17 film was authored under these four literals; derive_seeds does
    # not reproduce them, so the default scene_seed keeps them byte-for-byte.
    if rain_look.LOOK['scene_seed'] == 20260915:
        seeds = {'rain': 20260916, 'drips': 20260920, 'plants': 20260919, 'wind': 20260917}
    else:
        import spec as render_spec
        seeds = render_spec.derive_seeds(rain_look.LOOK['scene_seed'])
    component_report = component_materials.prepare(car_meshes, job.get('car'), wet=rainy, scale=scale)
    material_report = calibrate_materials(car_meshes, wet=rainy, scale=scale)
    tire_details = surface_detail.tire_sidewalls(car_meshes, scale, wet=rainy)
    night = job.get("scene", "turntable") == "night_garage"
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Render Studio World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.025, 0.035, 0.06, 1) if night else (0.15, 0.17, 0.20, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3 if night else 0.6
    scene.world = world

    bpy.ops.mesh.primitive_plane_add(size=span * 100, location=(center.x, center.y, low.z - 0.005 * scale))
    floor = bpy.context.object
    floor.name = "Render Studio Floor"
    floor.data.materials.append(material("Studio floor", (0.018, 0.023, 0.033) if night else (0.075, 0.083, 0.10), 0.22 if night else 0.32, 0.18))
    # Broad softboxes give the car's authored physical materials readable
    # reflections without touching those materials or replacing its textures.
    area_light("Key softbox", center + Vector((4, -3, 5)) * scale, center, 2400 * scale * scale, 5 * scale, (1.0, 0.96, 0.90), 2 * scale)
    area_light("Fill softbox", center + Vector((-4, -1, 3)) * scale, center, (1200 if night else 1800) * scale * scale, 4 * scale, (0.65, 0.78, 1.0) if night else (0.87, 0.93, 1.0), 2 * scale)
    area_light("Roof strip", center + Vector((0, 2, 6)) * scale, center, 2600 * scale * scale, 6 * scale, (0.80, 0.90, 1.0), 1.6 * scale)
    area_light("Rear rim", center + Vector((1, 5, 2.5)) * scale, center, 1700 * scale * scale, 4 * scale, (1.0, 0.72, 0.43) if night else (1.0, 1.0, 1.0), 1 * scale)

    scene_report = {}
    if rainy:
        for obj in list(scene.objects):
            if obj.type == 'LIGHT' or obj == floor:
                bpy.data.objects.remove(obj, do_unlink=True)
        scene_report = rain_scene.build(scene, center, low, scale, plant_seed=seeds['plants'])
        rain_scene.car_apron(center, extent, scale, rain_look.LOOK['car_apron'])
        component_report += component_materials.weathered_rotors(car_meshes, job.get('car'), scale)
        rain_look.environment(scene, center, low, scale)
        scene_report['filmTreatments'] = rain_look.car_materials(car_meshes, job.get('car'), scale)
        scene_report['roadWeathering'] = road_weathering.apply(car_meshes, low, high, scale, rain_look.LOOK)
        scene_report['waterBeads'] = add_water_beads(car_meshes, scale)
        rain_look.link_reflections(scene, car_meshes)
        rain_look.wheel_reflector(scene, car_meshes, center, extent, low, scale)
        rain_look.cabin_fill(scene, center, extent, low, scale)
        scene_report['lamps'] = [kind for kind, _mat, _shader in rain_look.lamps(car_meshes)]
    elif directed:
        scene_report['lampsOff'] = rain_look.switch_off_lamps(car_meshes)
    scene_report['detailedTires'] = tire_details
    scene_report['components'] = component_report

    resolution = job.get("resolution", [1280, 720])
    width, height = [int(value) for value in resolution]
    if job.get("aspect") == "9:16" and width > height:
        width, height = height, width
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = rain_look.LOOK['view_look'] if directed else "AgX - Medium High Contrast"
    except TypeError:
        pass
    fps = int(job.get("fps", 30))
    total = int(job.get("total_frames", job.get("totalFrames", round(float(job.get("duration_s", 6)) * fps))))
    first = int(job.get("frame_start", 1))
    scene.render.fps = fps
    scene.frame_start = first
    scene.frame_end = first + total - 1
    if rainy:
        import wet_detail
        import wind
        if rain_look.LOOK['falling_rain']:
            wet_detail.configure_ripple_animation(scene, first, total)
            scene_report['fallingRain'] = rain_atmosphere.build(scene, car_meshes, center, low, scale, first, total,
                                                                seed=seeds['rain'],
                                                                size=rain_look.LOOK['rain_size'], reach=rain_look.LOOK['rain_reach'],
                                                                backlight=rain_look.LOOK['rain_backlight'], glow=rain_look.LOOK['rain_glow'])
            for puddle in bpy.data.materials:
                if puddle.use_nodes and puddle.get('mv_animated_puddles'):
                    ripple = puddle.node_tree.nodes.get('Localized shallow-water ripple normal')
                    if ripple:
                        ripple.inputs['Distance'].default_value *= rain_look.LOOK['ripple_depth'] * rain_look.LOOK['ripple_scale']
                        ripple.inputs['Strength'].default_value = min(1.0, ripple.inputs['Strength'].default_value * 2.2)
                    # Wider, longer-waved rings for low cameras: at a grazing angle the 27 mm
                    # wavelets fall under a pixel and the bump filter removes them.
                    wider = rain_look.LOOK['ripple_scale']
                    for node in puddle.node_tree.nodes:
                        if node.label == 'Ring reach metres':
                            node.inputs[1].default_value *= wider
                        elif node.label in ('Ring envelope sharpness', 'Ring wave number'):
                            node.inputs[1].default_value /= wider
        else:
            # No drops, so no impact rings: the standing water lies still.
            for puddle in bpy.data.materials:
                if puddle.use_nodes and puddle.get('mv_animated_puddles'):
                    ripple = puddle.node_tree.nodes.get('Localized shallow-water ripple normal')
                    if ripple:
                        ripple.inputs['Strength'].default_value = 0
            scene_report['fallingRain'] = None
        if rain_look.LOOK['drips'] > 0:
            scene_report['drips'] = rain_atmosphere.drips(scene, car_meshes, center, extent, low, scale, first,
                                                          seed=seeds['drips'],
                                                          count=int(rain_look.LOOK['drips']), size=rain_look.LOOK['drip_size'],
                                                          glow=rain_look.LOOK['rain_glow'] * .4)
        scene_report['wind'] = wind.apply(scene, first, total, scale, rain_look.LOOK['wind'], rain_look.LOOK['wind_canopy'], seed=seeds['wind'])
    device = pick_engine(scene, job.get("engine", "EEVEE"), int(job.get("samples", 32)))
    if rainy and scene.render.engine == 'CYCLES':
        scene.cycles.max_bounces = 10
        scene.cycles.transmission_bounces = 8
        scene.cycles.transparent_max_bounces = 24
        scene.cycles.adaptive_threshold = rain_look.LOOK['adaptive_threshold']
        scene.cycles.sample_clamp_indirect = 5
        scene.cycles.seed = int(rain_look.LOOK['seed'])
        if rain_look.LOOK['denoise'] is not None:
            scene.cycles.use_denoising = bool(rain_look.LOOK['denoise'])
        if rain_look.LOOK['denoiser']:
            scene.cycles.denoiser = rain_look.LOOK['denoiser']
        if rain_look.LOOK['denoise_prefilter']:
            scene.cycles.denoising_prefilter = rain_look.LOOK['denoise_prefilter']
        print('DENOISE', scene.cycles.use_denoising, scene.cycles.denoiser, scene.cycles.denoising_prefilter, scene.cycles.denoising_input_passes)
        scene.cycles.use_animated_seed = bool(rain_look.LOOK['animated_seed'])
    scene.view_settings.exposure = rain_look.LOOK['exposure'] if directed else 0
    if rainy:
        scene_report['opticalFinishing'] = rain_look.compositor(scene, scale)
    camera_data = bpy.data.cameras.new("Render Studio Camera")
    camera_data.lens = 48
    camera_data.sensor_width = 36
    camera_data.sensor_fit = "HORIZONTAL"
    camera = bpy.data.objects.new("Render Studio Camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    hfov = 2 * math.atan(camera_data.sensor_width / (2 * camera_data.lens))
    vfov = 2 * math.atan(math.tan(hfov / 2) * height / width)
    radius = extent.length / 2
    distance = radius / math.sin(min(hfov, vfov) / 2) * 1.12
    camera_data.clip_start = max(scale * 0.01, 0.001)
    camera_data.clip_end = max(distance * 10, 100 * scale)
    elevation = math.radians(13 if night else 17)
    # A job from the studio carries the scene plan the user directed in the viewer.
    # Which camera runs it is the job's choice: the rain scene's five-shot operator is
    # a large part of that scene's look, so a handheld plan hands over to it, and
    # everything else traces the path drawn in the viewer.
    plan = job.get("plan")
    film = rainy and job.get("camera_programme", "film") == "film"
    if plan and not film:
        subject = scene_plan_camera.bounds((extent.x, extent.y, extent.z))
        ground_centre = (center.x, center.y, low.z)
        scene_plan_camera.animate(camera, plan, subject, ground_centre, first, total, fps)
        blur = plan["effects"]["motionBlur"]
        scene.render.use_motion_blur = blur > 0
        if blur > 0:
            scene.render.motion_blur_shutter = 0.5 * blur
        # The studio's light slider is in stops, which is exactly Blender's exposure.
        scene.view_settings.exposure = plan["lighting"]["exposure"]
        if rainy:
            # Rain atmosphere, but not the five-shot exposure and lamp ramps: those
            # are indexed by that operator's shots and mean nothing against a plan.
            rain_look.animate_reflections(scene, first, total)
            rain_look.distance_fog(scene, center, low, scale)
    elif film:
        film_camera.animate(camera, scene, center, extent, low, points, width, height, total, first, scale, car_meshes)
        if rain_look.LOOK['freeze_camera'] is not None:
            camera.animation_data_clear()
            camera.data.animation_data_clear()
            film_camera.pose(camera, center, extent, low, points, width, height, int(rain_look.LOOK['freeze_camera']), total, scale,
                             film_camera.anchors(car_meshes, center, extent, low), scene.render.fps)
        if rain_look.LOOK['probe_camera']:
            probe = rain_look.LOOK['probe_camera']
            camera.animation_data_clear()
            camera.data.animation_data_clear()
            camera.data.lens = probe.get('lens', 35)
            camera.data.dof.use_dof = True
            camera.data.dof.focus_object = None
            camera.data.dof.aperture_fstop = probe.get('fstop', 2.8)
            road = Vector((center.x, center.y, low.z))
            for offset in range(-1, total + 1):
                u = max(0.0, min(1.0, offset / max(1, total - 1)))
                u = u * u * (3 - 2 * u)
                seconds = offset / scene.render.fps
                shake = probe.get('shake', rain_look.LOOK['probe_shake'])
                drift = Vector((film_camera._wander(7.1, seconds, fast=.05), film_camera._wander(7.2, seconds, fast=.05), .6 * film_camera._wander(7.3, seconds, fast=.05))) * (.012 * shake)
                place = road + (Vector(probe['from']).lerp(Vector(probe.get('to', probe['from'])), u) + drift) * scale
                sway = Vector((film_camera._wander(7.4, seconds, fast=.05), film_camera._wander(7.5, seconds, fast=.05), film_camera._wander(7.6, seconds, fast=.05))) * (.01 * shake)
                aim = road + (Vector(probe['aim']).lerp(Vector(probe.get('aim_to', probe['aim'])), u) + sway) * scale
                camera.location = place
                camera.rotation_euler = (aim - place).to_track_quat('-Z', 'Y').to_euler()
                camera.data.dof.focus_distance = (aim - place).length
                camera.keyframe_insert(data_path='location', frame=first + offset)
                camera.keyframe_insert(data_path='rotation_euler', frame=first + offset)
                camera.data.keyframe_insert(data_path='dof.focus_distance', frame=first + offset)
        rain_look.animate_reflections(scene, first, total)
        rain_look.animate_exposure(scene, first, total)
        rain_look.animate_lamps(scene, first, total)
        rain_look.distance_fog(scene, center, low, scale)
    # Internal CLI proof mode is never accepted as an API job field. Render
    # representative poses before spending time on an entire movie.
    offsets = job.get('proof_offsets', list(range(total)))
    if job.get('save_blend'):
        scene.frame_set(first + offsets[0])
        bpy.ops.wm.save_as_mainfile(filepath=str(job_dir / 'scene.blend'))
    render_seconds = 0.0
    prepare_seconds = time.monotonic() - started
    progress(status="rendering", frame=0, totalFrames=total, progress=0.03, device=device)
    for output_index, offset in enumerate(offsets):
        frame = first + offset
        scene.frame_set(frame)
        # Rain films keep a stable motion-pass layout and full shutter. The
        # baked camera/light cuts occur only between exposure intervals.
        if not rainy and not plan:
            angle = math.radians(38) + math.tau * offset / total
            camera.location = center + Vector((math.sin(angle) * math.cos(elevation), -math.cos(angle) * math.cos(elevation), math.sin(elevation))) * distance
            camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(frames / f"frame_{first + output_index:06d}.png")
        frame_started = time.monotonic()
        bpy.ops.render.render(write_still=True)
        elapsed = time.monotonic() - frame_started
        render_seconds += elapsed
        if output_index == 0 or (output_index + 1) % 10 == 0 or output_index == len(offsets) - 1:
            # Atomic replacement prevents a browser from seeing a half-written
            # preview while it polls the latest completed frame.
            scene.render.image_settings.file_format = "JPEG"
            scene.render.image_settings.quality = 85
            temporary = job_dir / "latest-next.jpg"
            bpy.data.images["Render Result"].save_render(str(temporary), scene=scene)
            # A watermarked preset never exposes a clean still: the parent
            # pipeline stamps latest-raw.jpg into latest.jpg (watermark.py).
            temporary.replace(job_dir / ("latest-raw.jpg" if job.get("watermark") else "latest.jpg"))
            scene.render.image_settings.file_format = "PNG"
        progress(status="rendering", frame=output_index + 1, totalFrames=len(offsets), progress=0.03 + 0.90 * (output_index + 1) / len(offsets),
                 secondsPerFrame=round(render_seconds / (output_index + 1), 3), secondsRemaining=round((len(offsets) - output_index - 1) * render_seconds / (output_index + 1)),
                 sec=round(elapsed, 3), device=device)
    stats = {"totalFrames": len(offsets), "frameStart": first, "fps": fps, "resolution": [width, height], "device": device,
             "engine": scene.render.engine, "prepareSeconds": round(prepare_seconds, 3), "renderSeconds": round(render_seconds, 3),
             "scene": job.get('scene'), 'materials': material_report, 'sceneDetails': scene_report,
             'shots': list(film_camera.SHOT_NAMES) if film else ([shot['action'] for shot in plan['shots']] if plan else ['Orbit']), 'proofOffsets': job.get('proof_offsets')}
    (job_dir / "render-stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print("RENDER_DONE " + json.dumps(stats), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR " + str(error), flush=True)
        raise
