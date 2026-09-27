"""Repair map (spec §4.6, TIERS §3). Checker errors and failing TIERS [S] items become a report the
model can act on (code, path, message, fix). A few single-parameter craft items are fixed in place."""
import copy

from engine.catalog import clamp_number
from engine.craft_rules import score_script
from engine.issues import Issue

GENERIC = "Change the named field so it follows the hard rules and the menu."
ERROR_HINTS = {
    "bad_script": "Return one JSON object.", "llm_not_json": "Return exactly one JSON object matching the schema.",
    "llm_stop_refusal": "Write a scene script for the video only.",
    "llm_stop_max_tokens": "Return a shorter script: fewer assumptions and shots.",
    "bad_schema": GENERIC, "bad_seed": GENERIC, "bad_format": GENERIC, "bad_aspect": GENERIC,
    "bad_duration": GENERIC, "bad_fps": GENERIC,
    "bad_subject": "subject must be {placement, motion}.", "bad_effects": "effects must be a list of effect blocks.",
    "reserved_not_in_v1": "Remove it; audio does not exist yet (list it in unsupported instead).",
    "bad_placement": "placement is 'ground' or 'float'.",
    "motion_needs_profile": "Use motion 'static': this model lacks the fact that motion needs (see the message).",
    "clip_unavailable": "Use a clip index listed in the subject card's animationClips.",
    "bad_block_ref": "A block is {id, params} with an id from the menu.",
    "unknown_block": "Use a block id listed in the menu for that kind.",
    "director_block_forbidden": "That block is not on the menu. Pick a listed one.",
    "bad_purpose": "purpose is one of hook, establish, detail, motion, hero, packshot.",
    "transition_not_available": "Use transitionIn 'cut'.", "bad_transition": "Use transitionIn 'cut'.",
    "bad_target": "target is {marker: id} or {detail: index}.",
    "unknown_target": "Target a marker id from the job, or a detail index shown on the subject card.",
    "bad_focus": "focus is 'subject'.",
    "no_shots": "Add shots covering 0 to durationS.",
    "bad_shot_times": "Each shot needs numeric startS < endS.",
    "shots_not_contiguous": "Make each shot start where the previous one ends, from 0 to the job's durationS.",
    "direction_cadence": "Use the number of shots the message names: the job's pace is measured as cut.",
    "direction_opener": "Open (the first shot's camera) with the job direction's opener camera.",
    "direction_world": "Use the job direction's world block.",
    "shot_not_frame_aligned": "Put every shot boundary on a whole frame (a multiple of 1/fps).",
    "shot_too_short": "Make the shot at least 2 frames long; merge it with a neighbour.",
    "subject_size_unsupported": "Pick blocks whose subject size range contains the subject's longestM.",
    "aspect_unsupported": "Pick blocks that support the job's aspect.",
    "world_has_no_ground": "Use placement 'float' or a world with a ground.",
    "detail_target_off_centre": "Use move 'push' or a smaller slideFrac on that macro_detail shot, or another target.",
    "framing_unfixable": "Use a camera that frames the whole subject: a longer lens or a different block.",
    "camera_view_blocked": "Swing that camera's bearing so it stands on the subject's side of the world's kerb, "
                           "pavement or curb (down the street, not across it), or use a camera closer in.",
    "subject_left_frame": "The subject moves out of that shot: use a wider camera, a shorter motion, or a camera that follows it.",
    "coupling_removed": "Keep the coupled effect the message names (rain brings wet ground), or drop its parent too.",
    "effect_max_per_clip": "Use that effect once per clip.",
    "camera_max_per_clip": "Use that camera in one shot only; pick another camera for the other shots.",
    "camera_needs_motion": "A tracking camera needs the subject to move (drive, slide): use an orbit or a push for a still subject.",
    "lighting_world_mismatch": "Use a lighting block this world pairs with (the message lists them); a studio rig never lights an outdoor world.",
    "effect_needs_profile": "Remove that effect: this model lacks what it needs (see the message).",
    "effect_needs_world": "Remove that effect or use an outdoor world that has what the message names.",
    "effect_off_screen": "Set the effect's shot to the index of one of the clip's shots.",
    "effect_needs_source": "Remove lens_drops, or add rain to the clip (drops on the lens need rain).",
    "lens_drops_no_shot": "Remove lens_drops, or make one shot a full-framing shot for them.",
    "exclusive_effects": "Keep only one of the two effects the message names (rain or snow, not both).",
    "spawn_in_subject": "Move that effect's position param outside the subject.",
    "surface_state_continuity": "Remove surfaceState from the shot; the ground's state is one per clip.",
    "time_scale_weather": "Remove the time-scale param: weather runs at real time.",
    "path_through_world": "The motion travels farther than the world allows: shorten it, use motion 'static', or a world with a drive lane.",
    "motion_needs_ground": "Use placement 'ground' for that motion, or motion 'float_drift' / 'static'.",
    "motion_too_long": "Start the motion earlier or pick a faster/shorter one so it is still for the last 0.8 s.",
    "motion_too_fast": "Turn less (a smaller turnDeg / fewer spins) or take longer over it.",
    "spin_needs_camera_move": "Move the camera while the subject turns (arc_orbit, low_hero_push), never a locked or turntable camera.",
    "bad_unsupported": "unsupported is a list of {ask, capability}.",
    "seq_shot_count": "Use the number of shots the pace allows for this duration (see edit/sequence shotsPer10s).",
    "seq_shot_length": "Keep every shot inside edit/sequence shotLenS; split or merge shots.",
    "seq_median_length": "Balance shot lengths so the median is inside medianLenS.",
    "seq_bad_hook": "First shot: a full-framing hook or establish shot no longer than hookMaxS that shows the whole subject from its first frame (never reveal_rise).",
    "seq_no_detail": "Add a macro_detail shot.",
    "seq_bad_ending": "Last shot: a full-framing hero or packshot at least lastShotMinS long.",
    "seq_jump_cut": "Change azimuth by 30 degrees or more, or the framing size by 1.5x, across that cut.",
    "seq_no_still_ending": "Raise settleFrac on the last shot so it ends still for 1 s.",
    # Markers are system-owned (validated before any call), so the model cannot fix them: GENERIC.
    "bad_markers": GENERIC, "too_many_markers": GENERIC, "bad_marker": GENERIC, "bad_marker_id": GENERIC,
    "duplicate_marker_id": GENERIC, "bad_marker_text": GENERIC, "bad_marker_anchor": GENERIC,
    "bad_marker_time": GENERIC, "marker_off_subject": GENERIC, "bad_marker_part": GENERIC,
    "marker_part_mismatch": GENERIC, "marker_off_surface": GENERIC,
    "bad_realism": "Do not write realism; the system fills it.",
    "realism_not_always_on": "Do not write realism; the system fills it.",
}

S_REPAIRS = {  # TIERS §3: [S] failure -> the params that fix it
    "T1-X1": {"params": "shots", "hint": "No single-shot orbit over 180 degrees: use 3+ shots, sweeps of 90 degrees or less."},
    "T1-X3": {"params": "lighting.params", "hint": "Not flat: rimStrength above 0 and fillRatio 0.25-0.5, or reflection_rig."},
    "T2-01": {"params": "world.id", "hint": "Use a world with a ground or an environment."},
    "T2-03": {"params": "shots[*].camera.params.easing", "hint": "Ease every move."},
    "T2-04": {"params": "shots[*].camera.id", "hint": "Give every shot a motivated camera move."},
    "T2-05": {"params": "(compiler)", "hint": "By construction."},
    "T2-07": {"params": "effects", "hint": "Add haze_volume or use a studio world."},
    "T2-08": {"params": "grade", "hint": "Use a mood_grade preset (not identity)."},
    "T3-01": {"params": "shots", "hint": "Use 3-7 shots per 10 s."},
    "T3-02": {"params": "shots[*].startS/endS", "hint": "Median shot 1.0-3.0 s, none under 0.5 s, last at least 1.5 s."},
    "T3-03": {"params": "shots", "hint": "Use at least two shot sizes and one macro_detail shot."},
    "T3-04": {"params": "shots[*].camera.params.(start)azimuth(Offset)Deg", "hint": "Change azimuth 30+ degrees or size 1.5x at every cut."},
    "T3-05": {"params": "shots", "hint": "Keep a moving subject's screen direction across cuts."},
    "T3-11": {"params": "shots[*].camera.id", "hint": "One dominant move per shot: use a camera block with a declared move."},
    "T3-13": {"params": "shots[-1].camera.params.settleFrac", "hint": "End the last move in 1 s of stillness."},
    "T3-14": {"params": "shots[*].camera.params.sweepDeg", "hint": "Arc no faster than 80 degrees per second: smaller sweep or longer shot."},
    "T3-16": {"params": "shots[-1]", "hint": "End on a full-framing hero or packshot of at least 1.5 s."},
    "T3-21": {"params": "shots[*].camera.params.fstop", "hint": "Full vehicle frames: f/8 so the whole car is sharp."},
    "V-C02": {"params": "shots[*].camera.params.lensMm", "hint": "Full vehicle frames: 28 mm or longer."},
    "T4-02": {"params": "(no block yet)", "hint": "Not available in v1."},
    "T4-03": {"params": "(no block yet)", "hint": "Not available in v1."},
}
AUTO_FIX = ("T2-03", "T3-13", "V-C02", "T3-21")
_TIER = (("T1-", "T1"), ("T2-", "T2"), ("T3-", "T3"), ("V-", "T3"), ("T4-", "T4"))
_ORDER = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}


def _tier(iid):
    return next((t for p, t in _TIER if iid.startswith(p)), "T4")


def craft_failures(script, profile, catalog, target="T3"):
    return [r for r in score_script(script, profile, catalog)
            if r.status == "fail" and _ORDER[_tier(r.id)] <= _ORDER[target]]


def auto_fix_craft(script, fails, profile, catalog):
    s, issues = copy.deepcopy(script), []
    ids = {f.id for f in fails}

    def setp(i, key, value, code):
        cam = s["shots"][i]["camera"]
        spec = catalog.get("camera", cam["id"])["params"].get(key)
        if spec is None:
            return
        if spec["type"] == "number":
            value = clamp_number(spec, value)
        old = cam["params"].get(key, spec["default"])
        if old != value:
            cam["params"][key] = value
            issues.append(Issue(code, f"shots[{i}].camera.params.{key}", f"{old} -> {value}", "repaired"))

    full = [i for i, sh in enumerate(s["shots"]) if catalog.get("camera", sh["camera"]["id"])["framing"] == "full"]
    if "T2-03" in ids:
        for i in range(len(s["shots"])):
            setp(i, "easing", "in_out_cubic", "craft_eased")
    if "T3-13" in ids:
        last = s["shots"][-1]
        cur = last["camera"]["params"].get("settleFrac", 0.0)
        setp(len(s["shots"]) - 1, "settleFrac", max(cur, 1.1 / (last["endS"] - last["startS"])), "craft_settled")
    for iid, key, floor, code in (("V-C02", "lensMm", 28.0, "craft_lens_28"), ("T3-21", "fstop", 8.0, "craft_deep_focus")):
        if iid in ids:
            for i in full:
                spec = catalog.get("camera", s["shots"][i]["camera"]["id"])["params"][key]
                setp(i, key, max(floor, s["shots"][i]["camera"]["params"].get(key, spec["default"])), code)
    return s, issues


def problems(issues, craft=()):
    out = [{"code": i.code, "path": i.path, "message": i.message, "fix": ERROR_HINTS.get(i.code, GENERIC)}
           for i in issues if i.severity == "error"]
    out += [{"code": f.id, "path": S_REPAIRS.get(f.id, {}).get("params", ""),
             "message": f"craft rule {f.id} failed" + (f": {f.detail}" if f.detail else ""),
             "fix": S_REPAIRS.get(f.id, {}).get("hint", GENERIC)} for f in craft]
    return out
