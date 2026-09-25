"""Foreground occluder cards a camera path asks for (profile_slide foreground, Task 83). Runs in Blender.

For each shot whose camera path.py defines foreground(params, profile, outdoor) and returns a card, one
upright dark card is built where engine/foreground_plan put it (from the camera's own posed subject profile,
clear of the live subject for the whole shot; a post silhouette standing on the ground), tagged
valora_block camera/<id>, and keyed visible only inside its shot: hidden from half a frame before the shot's
first frame to half a frame after its last, so no exposure of a neighbouring shot sees it across a cut. The
camera's depth of field (focus on the subject) blurs it."""
import bpy

CARD_RGB = (0.018, 0.018, 0.02)   # (eng) a dark, matte silhouette


def _key_visible(ob, frames):
    """frames: [(frame, visible)] - hide_render / hide_viewport keyed constant at those (sub)frames."""
    for f, vis in frames:
        ob.hide_render = ob.hide_viewport = not vis
        ob.keyframe_insert("hide_render", frame=f)
        ob.keyframe_insert("hide_viewport", frame=f)


def build_foreground(scene, script, profile, catalog):
    from engine.blender import set_parts as P
    from engine.foreground_plan import plan_foreground
    world = catalog.get("world", script["world"]["id"]) or {}
    fps, out = script["format"]["fps"], []
    for i, card in plan_foreground(script, profile, catalog, bool(world.get("outdoor"))):
        sh = script["shots"][i]
        bid = sh["camera"]["id"]
        a, b, c, d = card["corners"]            # (-w, 0), (-w, top), (+w, 0), (+w, top)
        ob = P.mesh(scene, f"valora_foreground_{i}", f"camera/{bid}", [a, c, d, b], [(0, 1, 2, 3)],
                    [P.mat(f"valora_foreground_{i}", CARD_RGB, 0.9)])
        ob.visible_glossy = False                 # an occluder in front of the lens, not a set piece to reflect
        first, last = int(round(sh["startS"] * fps)) + 1, int(round(sh["endS"] * fps))
        _key_visible(ob, [(0, False), (first - 0.5, True), (last + 0.5, False)])
        keep = scene.frame_current
        seen = {}
        for f in (first, (first + last) // 2, last, first - 1, last + 1):   # read the keyed visibility back
            scene.frame_set(f)
            seen[f] = not ob.hide_render
        scene.frame_set(keep)
        out.append({"shot": i, "name": ob.name, "kind": card["kind"], "center": list(card["center"]),
                    "width": card["width"], "height": card["height"], "frames": [first, last],
                    "visibleInShot": seen[first] and seen[(first + last) // 2] and seen[last],
                    "hiddenOutside": not seen[first - 1] and not seen[last + 1]})
    return out
