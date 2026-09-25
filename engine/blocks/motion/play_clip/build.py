"""Play clip `clip` of the subject's own animation on NLA strips over the whole video (mode: loop, once,
pingpong; auto loops a seamless clip and ping-pongs any other, engine.clips.resolve_mode).
Clip indices follow scene_io.subject_actions() over the clips rest_animation recorded for the imported
subject only - the same order, dedupe and filter ingest used (blender_extract + measure._clips).
NLA API names confirmed on Blender 5.0.1 (Task 29 probe): tracks.new(), strips.new(name, start, action),
strip.action_slot, action_frame_start/end, scale, repeat, frame_start_ui."""
import math


def build(ctx):
    from engine.blender.scene_io import rested_clips, subject_actions
    from engine.clips import resolve_mode, strip_plan
    raw = rested_clips(ctx.scene)                 # the subject's clips, recorded by rest_animation (compiler)
    fps_in = float(ctx.scene["valora_import_fps"])
    actions = subject_actions(raw, fps_in)        # the same index ingest gave (dedupe + clip_kept)
    i = int(round(ctx.params["clip"]))
    clips = ctx.profile.animationClips
    if not 0 <= i < len(actions) or i >= len(clips):
        raise RuntimeError(f"clip {i} not found ({len(actions)} clips): the checker should have refused this script")
    if abs(clips[i]["fps"] - fps_in) > 1e-6:
        raise RuntimeError(f"clip {i} was measured at {clips[i]['fps']} fps but the model imports at {fps_in}: "
                           "the profile is stale, re-ingest the model")
    action = actions[i]
    fps = ctx.script["format"]["fps"]
    start, end = action.frame_range
    scale = fps / clips[i]["fps"] / ctx.params["speed"]
    mode = resolve_mode(ctx.params.get("mode", "auto"), clips[i].get("seamless"))
    segs = strip_plan((end - start) * scale, ctx.script["format"]["durationS"] * fps + 2,
                      ctx.params["offsetS"] * fps, mode)
    for ad, act, slot, _t in raw:
        if act is not action:
            continue
        track = ad.nla_tracks.new()
        track.name = "valora_clip"
        prev_end = 1.0
        for k, (s0, repeat, reverse) in enumerate(segs):
            # strips.new takes an int start that must be free: create past the last strip, then move it
            strip = track.strips.new(f"valora_clip{k}", int(math.ceil(prev_end)) + 5, action)
            if slot is not None and hasattr(strip, "action_slot"):
                strip.action_slot = slot
            strip.action_frame_start, strip.action_frame_end = start, end
            strip.scale, strip.repeat, strip.use_reverse = scale, repeat, reverse
            strip.extrapolation = "HOLD" if k == 0 else "NOTHING"  # 'once' holds the last pose after its end
            strip.frame_start_ui = s0              # frame_start alone leaves the strip inconsistent (5.0.1)
            prev_end = strip.frame_end
        ad.use_nla = True
