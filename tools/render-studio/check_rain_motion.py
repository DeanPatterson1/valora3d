"""CPU-only contracts for evaluated rain instances and subframe collision.

Run with Blender --background --factory-startup --python-exit-code 1 --python.
An optional path after ``--`` selects the JSON report destination. This creates
only a synthetic collider in memory; it never loads/saves a production scene or
calls the renderer.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import rain_atmosphere


def evaluated_instances(scene, frame):
    whole = math.floor(frame)
    scene.frame_set(whole, subframe=frame - whole)
    graph = bpy.context.evaluated_depsgraph_get()
    # RNA iterator entries expire on the next iteration; retain value copies.
    return {tuple(instance.persistent_id): instance.matrix_world.copy()
            for instance in graph.object_instances if instance.is_instance}


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) > 1:
        raise ValueError('Expected at most one JSON report path')
    destination = Path(args[0]).resolve() if args else ROOT / 'checks/black-rain-final/rain-motion-contract.json'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
    collider = bpy.context.object
    collider.name = 'Rain contract synthetic car collider'
    bpy.context.view_layer.update()
    scene = bpy.context.scene
    first, total, fps, scale = 1, 144, 24, 1.0
    scene.render.fps = fps
    construction = rain_atmosphere.build(
        scene, [collider], Vector((0, 0, 1)), Vector((-1, -1, 0)),
        scale, first, total,
    )
    assert construction['interceptedColumns'] > 0
    assert construction['temporalWrap'] is False
    droplets = bpy.data.objects['Rain — falling droplets']
    light = bpy.data.objects['Rain — falling-water backlight']
    receivers = light.light_linking.receiver_collection
    assert receivers is not None and set(receivers.objects) == {droplets}
    water = bpy.data.materials['Rain — airborne water'].node_tree.nodes.get('Principled BSDF')
    assert abs(water.inputs['IOR'].default_value - 1.333) < 1e-5
    assert water.inputs['Transmission Weight'].default_value == 1

    reference = evaluated_instances(scene, first)
    assert len(reference) == construction['drops']
    samples = []
    # Include the half-shutter endpoints outside the nominal first/last frames.
    for frame in (0.75, 1, 1.25, 60.125, 144, 144.25):
        instances = evaluated_instances(scene, frame)
        assert instances.keys() == reference.keys(), 'Rain instance identity/topology changed'
        expected_z = -6.5 * scale * (frame - first) / fps
        error = max((matrix.translation - reference[key].translation
                     - Vector((0, 0, expected_z))).length
                    for key, matrix in instances.items())
        assert error < 2e-5 * scale, (frame, error)
        active = [matrix for matrix in instances.values()
                  if max(matrix.to_scale()) > 1e-8 * scale]
        inside = [matrix for matrix in active
                  if abs(matrix.translation.x) < 1
                  and abs(matrix.translation.y) < 1
                  and matrix.translation.z < 2]
        below_ground = [matrix for matrix in active if matrix.translation.z < 0]
        assert not inside, (frame, 'Visible rain entered collider', len(inside))
        assert not below_ground, (frame, 'Visible rain crossed ground', len(below_ground))
        samples.append({
            'frame': frame,
            'instanceCount': len(instances),
            'activeInstanceCount': len(active),
            'activeInsideCollider': len(inside),
            'activeBelowGround': len(below_ground),
            'expectedZDisplacementMetres': expected_z,
            'maximumTrajectoryErrorMetres': error,
        })

    source = ROOT / 'rain_atmosphere.py'
    report = {
        'status': 'pass',
        'checkedAtUtc': datetime.now(timezone.utc).isoformat(),
        'blenderVersion': bpy.app.version_string,
        'evaluation': 'CPU dependency graph; no rendering',
        'source': str(source),
        'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'collider': {'type': 'synthetic cube', 'low': [-1, -1, 0], 'high': [1, 1, 2]},
        'job': {'first': first, 'totalFrames': total, 'fps': fps, 'scale': scale},
        'construction': construction,
        'rainOnlyBacklight': True,
        'waterIor': water.inputs['IOR'].default_value,
        'stableInstanceIdentity': True,
        'samples': samples,
        'limitations': 'Synthetic collider and evaluated instance motion only; rendered blur, visibility, and final film appearance need visual inspection.',
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('PASS: stable rain instances, 6.5 m/s subframe motion, car/ground interception and rain-only backlight')
    print('REPORT ' + str(destination))


if __name__ == '__main__':
    main()
