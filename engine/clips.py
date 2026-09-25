"""Pure helpers for the subject's own animation clips (play_clip). No bpy: ingest, the director and the
Blender block all import them, so they agree on which clips exist and how one is played."""
import math

MIN_CLIP_S = 0.25        # (eng) shorter clips are pose stubs, not performances; a 1-frame one would also
                         # need thousands of NLA repeats to fill a video
MAX_NLA_REPEAT = 1000.0  # NlaStrip.repeat hard_max, Blender 5.0.1 (bl_rna probe 2026-09-24); larger values clamp
MODES = ("auto", "loop", "once", "pingpong")
CLIP_MAP_VERSION = 2     # the clip index contract: 2 = clip_kept filter + one entry per action (2026-09-25).
                         # A profile clip without it (or older) may name a different action: re-ingest
ROOT_MOTION_FRAC = 0.05  # (eng) root horizontal travel over one clip, x the posed subject's longest side,
                         # above which the clip moves the subject (a walk), not just its limbs
STALE_NOTE = "This model's animation was measured by an older version, so it is shown still: re-ingest the model."

# A movement ask -> the clip-name stems that perform it (lowercase substrings of nameHint).
ASK_STEMS = (
    (("walk", "stroll", "strut", "march"), ("walk", "stroll", "strut", "march")),
    (("run", "jog", "sprint"), ("run", "jog", "sprint")),
    (("danc",), ("danc", "dance")),
    (("jump", "hop", "leap"), ("jump", "hop", "leap")),
    (("wav", "greet", "hello"), ("wav", "greet", "hello")),
    (("idle", "breath", "stand"), ("idle", "breath", "stand")),
    (("sit",), ("sit",)),
    (("fly", "flap", "flies", "flying"), ("fly", "flap")),
    (("swim",), ("swim",)),
    (("punch", "kick", "attack", "fight"), ("punch", "kick", "attack", "fight")),
    (("spin", "turn", "twirl"), ("spin", "turn", "twirl")),
    (("climb",), ("climb",)),
    (("crouch", "sneak"), ("crouch", "sneak")),
    (("fall",), ("fall",)),
)
CLIP_TAG = "motion.character_clip"


def clip_kept(frame_start, frame_end, fps):
    """Whether a clip counts at all. Ingest (measure._clips) and play_clip (Blender) share this filter,
    so clip index i names the same action on both sides."""
    return fps > 0 and (frame_end - frame_start) / fps >= MIN_CLIP_S - 1e-9


def clips_current(clips):
    """Whether a profile's clips were measured with the current clip map (index i names the same action
    in ingest and in play_clip). Empty -> False."""
    return bool(clips) and all(c.get("clipMapVersion") == CLIP_MAP_VERSION for c in clips)


def plays_in_place(clip, mode):
    """A root-motion clip that will loop (mode loop, or auto on a seamless clip) plays in place: its root's
    net horizontal travel is taken out, or each loop would teleport the subject back to its start."""
    return bool(clip.get("rootMotion")) and resolve_mode(mode, clip.get("seamless")) == "loop"


def in_place_line(clips, motion):
    """The assumption line for a play_clip motion whose clip plays in place, else None."""
    if not isinstance(motion, dict) or motion.get("id") != "play_clip":
        return None
    params = motion.get("params") or {}
    try:
        i = int(round(params.get("clip", 0)))
    except (TypeError, ValueError):
        return None
    if not 0 <= i < len(clips) or not plays_in_place(clips[i], params.get("mode", "auto")):
        return None
    return f"clip {i} walks forward, so it plays in place (a loop would jump back each cycle)"


def choose_clip(asks, clips):
    """Index of the clip a prompt's movement asks mean: the first clip (lowest index) whose name contains
    a stem the ask names, else the longest clip (ties: lowest index). Deterministic; names are untrusted
    hints and only ever select among measured clips."""
    if not clips:
        return 0
    texts = [str(a.get("ask", "")).lower() for a in asks if a.get("capability") == CLIP_TAG]
    stems = [s for t in texts for ask_stems, name_stems in ASK_STEMS if any(k in t for k in ask_stems)
             for s in name_stems]
    for c in clips:
        name = str(c.get("nameHint", "")).lower()
        if stems and any(s in name for s in stems):
            return c["index"]
    best = max(clips, key=lambda c: (c.get("durationS", 0.0), -c["index"]))
    return best["index"]


def resolve_mode(mode, seamless):
    """'auto' loops a clip whose last pose matches its first (or whose seam is unknown: profiles measured
    before 2026-09-25) and plays any other clip forwards then backwards: a loop would snap back to the
    first pose once per cycle, and a hold would freeze the subject for most of the video."""
    if mode != "auto":
        return mode
    return "pingpong" if seamless is False else "loop"


def strip_plan(loop_frames, video_frames, offset_frames, mode):
    """NLA segments [(frame_start, repeat, reversed)] covering frames 1 - offset .. 1 + video, back to back.
    `loop_frames` is one pass of the clip in scene frames. Each repeat stays <= MAX_NLA_REPEAT."""
    start = 1.0 - offset_frames
    if mode == "once":
        return [(start, 1.0, False)]
    passes = max(1, math.ceil((video_frames + offset_frames) / max(loop_frames, 1e-6) - 1e-9) + 1)
    segs = []
    if mode == "pingpong":
        for k in range(passes):
            segs.append((start + k * loop_frames, 1.0, k % 2 == 1))
        return segs
    done = 0
    while done < passes:
        r = min(MAX_NLA_REPEAT, passes - done)
        segs.append((start + done * loop_frames, float(r), False))
        done += r
    return segs


def swept_profile(profile, script):
    """The profile to frame and place a play_clip script with. A root-motion clip that does NOT loop in place
    (once, pingpong, auto on a non-seamless clip) walks off the in-place box ingest measured: its bounds become
    the union of the in-place box and that box moved by the clip's travel (profile rootTravelM, placed metres)
    times the share of one pass the video plays. loop_in_place takes out exactly that linear ramp, so the real
    pose at pass share u is the in-place pose + travel * u and the two boxes contain every played pose.
    Placement (sourceCenter) is unchanged: the walk starts where the subject stands. Returns `profile` itself
    when nothing travels (no clip motion, loop mode, no root motion, or a profile without rootTravelM) or when
    it is already swept."""
    from dataclasses import replace
    if getattr(profile, "_swept", False) or not isinstance(script, dict):
        return profile
    motion = (script.get("subject") or {}).get("motion")
    if not isinstance(motion, dict) or motion.get("id") != "play_clip":
        return profile
    params = motion.get("params") or {}
    try:
        i = int(round(params.get("clip", 0)))
    except (TypeError, ValueError):
        return profile
    clips = profile.animationClips
    if not 0 <= i < len(clips):
        return profile
    clip, mode = clips[i], params.get("mode", "auto")
    travel = clip.get("rootTravelM")
    if not clip.get("rootMotion") or not travel or plays_in_place(clip, mode):
        return profile
    pass_s = float(clip.get("durationS") or 0.0) / float(params.get("speed", 1.0) or 1.0)
    played = float((script.get("format") or {}).get("durationS", 0.0)) + float(params.get("offsetS", 0.0))
    share = 1.0 if pass_s <= 0 else min(1.0, max(0.0, played / pass_s))
    shift = [float(travel[0]) * share, float(travel[1]) * share, 0.0]
    lo = [round(min(a, a + d), 6) for a, d in zip(profile.boundsMin, shift)]
    hi = [round(max(b, b + d), 6) for b, d in zip(profile.boundsMax, shift)]
    out = replace(profile, boundsMin=lo, boundsMax=hi, sizeM=[round(b - a, 6) for a, b in zip(lo, hi)])
    out._swept = True
    return out
