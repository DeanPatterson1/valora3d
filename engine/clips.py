"""Pure helpers for the subject's own animation clips (play_clip). No bpy: ingest, the director and the
Blender block all import them, so they agree on which clips exist and how one is played."""
import math

MIN_CLIP_S = 0.25        # (eng) shorter clips are pose stubs, not performances; a 1-frame one would also
                         # need thousands of NLA repeats to fill a video
MAX_NLA_REPEAT = 1000.0  # NlaStrip.repeat hard_max, Blender 5.0.1 (bl_rna probe 2026-09-24); larger values clamp
MODES = ("auto", "loop", "once", "pingpong")

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
