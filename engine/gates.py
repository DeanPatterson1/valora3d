"""Registry of checker/repair codes (phase 5 Task 52). The growth contract names gates by these codes.

Generated from the tree at Task 52 by the scan in engine/tests/test_gates_registry.py (literal Issue(...)
calls, the err() helper in engine/sequence.py, marker error tuples in engine/markers.py, and the dynamic
codes listed there). No code is emitted with two severities today; if one ever is, keep the stricter."""
from engine.issues import SEVERITIES  # noqa: F401  ("info", "repaired", "warning", "error")

CODES = {
    # --- phases 1-4 (generated from the tree at Task 52; keep sorted) ---
    "aspect_unsupported": "error",
    "bad_aspect": "error",
    "bad_block_ref": "error",
    "bad_duration": "error",
    "bad_effects": "error",
    "bad_focus": "error",
    "bad_format": "error",  # dynamic, built in engine/script.py
    "bad_fps": "error",
    "bad_marker": "error",
    "bad_marker_anchor": "error",
    "bad_marker_id": "error",
    "bad_marker_part": "error",
    "bad_marker_text": "error",
    "bad_marker_time": "error",
    "bad_markers": "error",
    "bad_placement": "error",
    "bad_purpose": "error",
    "bad_realism": "error",
    "bad_schema": "error",
    "bad_script": "error",
    "bad_seed": "error",
    "bad_shot_times": "error",
    "bad_subject": "error",  # dynamic, built in engine/script.py
    "bad_target": "error",
    "bad_transition": "error",
    "bad_unsupported": "error",
    "camera_distance_adjusted": "repaired",
    "clip_unavailable": "error",
    "craft_deep_focus": "repaired",  # dynamic, built in engine/director/repair.py
    "craft_eased": "repaired",  # dynamic, built in engine/director/repair.py
    "craft_lens_28": "repaired",  # dynamic, built in engine/director/repair.py
    "craft_settled": "repaired",  # dynamic, built in engine/director/repair.py
    "detail_slide_narrowed": "repaired",
    "detail_target_defaulted": "repaired",
    "detail_target_off_centre": "error",
    "detail_target_surface": "warning",
    "direction_cadence": "error",
    "direction_drift": "info",
    "direction_enforced": "repaired",
    "direction_opener": "error",  # dynamic, built in engine/director/adherence.py
    "direction_world": "error",  # dynamic, built in engine/director/adherence.py
    "director_block_forbidden": "error",
    "duplicate_marker_id": "error",
    "effect_duplicate_dropped": "repaired",
    "effects_capped": "repaired",
    "ending_settled": "repaired",
    "framing_unfixable": "error",
    "jump_cut_rotated": "repaired",
    "llm_bad_reply": "error",
    "llm_key_dropped": "repaired",
    "llm_not_json": "error",
    "llm_stop_max_tokens": "error",  # dynamic, built in engine/director/pipeline.py
    "llm_stop_refusal": "error",  # dynamic, built in engine/director/pipeline.py
    "llm_too_deep": "error",
    "marker_converted": "repaired",
    "marker_off_subject": "error",
    "marker_off_surface": "error",
    "marker_part_mismatch": "error",
    "marker_snapped": "repaired",
    "motion_needs_profile": "error",
    "no_shots": "error",
    "owned_field_overwritten": "repaired",
    "param_bad_enum": "repaired",
    "param_bad_type": "repaired",
    "param_clamped": "repaired",
    "param_default": "repaired",
    "param_unknown_dropped": "repaired",
    "purpose_inferred": "repaired",
    "realism_applied": "info",
    "realism_not_always_on": "error",
    "realism_not_applicable": "info",
    "realism_param_capped": "info",
    "realism_param_ignored": "info",
    "realism_skipped_low_confidence": "info",
    "requested_motion_applied": "repaired",
    "reserved_not_in_v1": "error",
    "seq_bad_ending": "error",
    "seq_bad_hook": "error",
    "seq_jump_cut": "error",
    "seq_median_length": "error",
    "seq_no_detail": "error",
    "seq_no_still_ending": "error",
    "seq_shot_count": "error",
    "seq_shot_length": "error",
    "shot_not_frame_aligned": "error",
    "shot_snapped": "repaired",
    "shot_time_snapped": "repaired",
    "shot_too_short": "error",
    "shots_not_contiguous": "error",
    "subject_size_unsupported": "error",
    "too_many_markers": "error",
    "transition_not_available": "error",
    "unknown_block": "error",
    "unknown_target": "error",
    "unsupported_merged": "repaired",
    "wind_defaulted": "info",
    "wind_from_script": "info",
    "world_has_no_ground": "error",
    # --- phase 5 ---
    "coupled_added": "repaired",  # Task 57
    "coupled_skipped": "info",  # Task 57
    "coupling_removed": "error",  # Task 57
    "effect_max_per_clip": "error",  # Task 57
    "effect_needs_profile": "error",  # Task 57
    "effect_needs_world": "error",  # Task 57
    "effect_off_screen": "error",  # Task 57
    "effect_needs_source": "error",  # Task 68: lens_drops without rain
    "lens_drops_moved": "repaired",  # Task 68: off a detail shot
    "lens_drops_no_shot": "error",  # Task 68: every shot is a detail shot
    "exclusive_effects": "error",  # Task 57
    "motion_travel_capped": "repaired",  # Task 56
    "path_through_world": "error",  # Task 56
    "spawn_in_subject": "error",  # Task 57
    "subject_left_frame": "error",  # Task 56
    "surface_state_continuity": "error",  # Task 57
    "time_scale_weather": "error",  # Task 57
    "wind_implausible": "warning",  # Task 57
}
