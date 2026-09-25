"""Rulebook part 3: hard rules. Each names the issue codes that enforce it (engine spec §8
`enforced_by`). A rule no code enforces belongs in the taste guide instead (spec §4.4)."""
HARD_RULES = (
    {"id": "HR-01", "text": "Use only block ids from the menu, and keep every number inside that block's range.",
     "enforced_by": ("unknown_block", "param_clamped")},
    {"id": "HR-02", "text": "Shots are contiguous from 0 to the job's durationS and start and end on whole frames "
                            "(multiples of 1/fps); each shot is at least 2 frames.",
     "enforced_by": ("shots_not_contiguous", "shot_not_frame_aligned", "shot_too_short")},
    {"id": "HR-03", "text": "Every world, lighting and camera block must support the subject's size.",
     "enforced_by": ("subject_size_unsupported",)},
    {"id": "HR-04", "text": "placement 'ground' needs a world with a ground.", "enforced_by": ("world_has_no_ground",)},
    {"id": "HR-05", "text": "focus is always 'subject'.", "enforced_by": ("bad_focus",)},
    {"id": "HR-06", "text": "No audio: it does not exist yet.", "enforced_by": ("reserved_not_in_v1",)},
    {"id": "HR-07", "text": "transitionIn is always 'cut'; other transitions do not exist yet.",
     "enforced_by": ("transition_not_available",)},
    {"id": "HR-08", "text": "A shot target is {marker: <a given marker id>} or {detail: <index from the subject "
                            "card>}, and it must exist.", "enforced_by": ("unknown_target",)},
    {"id": "HR-09", "text": "purpose is one of hook, establish, detail, motion, hero, packshot.",
     "enforced_by": ("bad_purpose",)},
    {"id": "HR-10", "text": "With the sequence edit block: open on a full-frame hook, include at least one detail "
                            "shot, keep each shot inside the block's shotLenS, and end on a full-frame hero or "
                            "packshot.", "enforced_by": ("seq_no_detail", "seq_bad_hook", "seq_bad_ending",
                                                         "seq_shot_length")},
    {"id": "HR-11", "text": "Markers are given by the system; you only target them by id.",
     "enforced_by": ("bad_marker_text", "marker_off_subject")},
    {"id": "HR-12", "text": "The camera stays outside the subject's bounds plus 10% and keeps the whole subject in "
                            "frame on full shots; the checker moves a camera that breaks this.",
     "enforced_by": ("camera_distance_adjusted",)},
    {"id": "HR-13", "text": "Everything the prompt or a marker asks for that no block can do goes in `unsupported` "
                            "as {ask, capability}; never pretend it is in the video.",
     "enforced_by": ("bad_unsupported", "director:unsupported_merged")},
    {"id": "HR-14", "text": "Choose only blocks listed in the menu (harness-only blocks are never allowed).",
     "enforced_by": ("director:director_block_forbidden",)},
    {"id": "HR-15", "text": "Do not write schema, seed, direction, prompt, format, markers or realism; the system fills them.",
     "enforced_by": ("director:owned_field_overwritten",)},
)


def render_hard_rules():
    lines = ["# 3. Hard rules",
             "The checker enforces every one of these. Breaking one costs a repair round; the codes in "
             "brackets are what the checker report will say."]
    for r in HARD_RULES:
        lines.append(f"- {r['id']} {r['text']} [{', '.join(r['enforced_by'])}]")
    return "\n".join(lines) + "\n"
