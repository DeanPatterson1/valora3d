"""Play clip `clip` of the subject's own animation on an NLA strip, looped over the whole video.
Clip indices follow engine.blender.scene_io.animation_clips() filtered to duration > 0, one entry per
action - the same order and filter ingest used (blender_extract dedupe + engine/ingest/measure._clips).
NLA API names confirmed on Blender 5.0.1 (Task 29 probe): tracks.new(), strips.new(name, start, action),
strip.action_slot, action_frame_start/end, scale, repeat, frame_start_ui."""
import math


def build(ctx):
    from engine.blender.scene_io import animation_clips
    raw = [c for c in animation_clips(ctx.scene) if c[1].frame_range[1] > c[1].frame_range[0]]
    actions = []                                  # one clip = one action, played on every owner it drives
    for c in raw:
        if c[1] not in actions:
            actions.append(c[1])
    i = int(round(ctx.params["clip"]))
    if not 0 <= i < len(actions) or i >= len(ctx.profile.animationClips):
        raise RuntimeError(f"clip {i} not found ({len(actions)} clips): the checker should have refused this script")
    for ad, _action, _slot, _t in raw:            # silence everything first
        ad.action = None
        ad.use_nla = False
        for tr in ad.nla_tracks:
            tr.mute = True
    action = actions[i]
    fps = ctx.script["format"]["fps"]
    start, end = action.frame_range
    scale = fps / ctx.profile.animationClips[i]["fps"] / ctx.params["speed"]
    video = ctx.script["format"]["durationS"] * fps + 2
    offset = ctx.params["offsetS"] * fps
    for ad, act, slot, _t in raw:
        if act is not action:
            continue
        track = ad.nla_tracks.new()
        track.name = "valora_clip"
        strip = track.strips.new("valora_clip", 1, action)
        if slot is not None and hasattr(strip, "action_slot"):
            strip.action_slot = slot
        strip.action_frame_start, strip.action_frame_end = start, end
        strip.scale = scale
        strip.repeat = float(max(1, math.ceil((video + offset) / max((end - start) * scale, 1e-6)) + 1))
        strip.frame_start_ui = 1 - offset          # frame_start alone leaves the strip inconsistent (5.0.1)
        ad.use_nla = True
