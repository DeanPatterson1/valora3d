"""Pure grade plans for neutral_film and mood_grade; engine/blender/grade.py realises them.
Preset numbers are (eng) starting values: calibrate via harness items T2-08, T3-08, T3-19, T3-20."""

# Look names differ across Blender versions; the realiser tries them in order ("None" last).
AGX_LOOKS = {
    "none": ["None"],
    "base": ["AgX - Base Contrast", "Base Contrast", "None"],
    "medium_high": ["AgX - Medium High Contrast", "Medium High Contrast", "None"],
    "high": ["AgX - High Contrast", "High Contrast", "None"],
    "very_high": ["AgX - Very High Contrast", "Very High Contrast", "None"],
}

PRESETS = {
    "clean":        {"agx": "base",        "lift": (1.0, 1.0, 1.0),      "gain": (1.0, 1.0, 1.0),    "sat": 1.00, "bloom": 0.10, "halation": 0.00, "vignette": 0.00},
    "premium_dark": {"agx": "medium_high", "lift": (0.985, 0.985, 0.99), "gain": (1.0, 1.0, 1.0),    "sat": 0.95, "bloom": 0.15, "halation": 0.10, "vignette": 0.25},
    "warm_golden":  {"agx": "medium_high", "lift": (1.0, 0.995, 0.985),  "gain": (1.04, 1.0, 0.93),  "sat": 1.08, "bloom": 0.20, "halation": 0.20, "vignette": 0.15},
    "teal_night":   {"agx": "high",        "lift": (0.98, 1.0, 1.02),    "gain": (1.03, 1.0, 0.96),  "sat": 1.05, "bloom": 0.25, "halation": 0.25, "vignette": 0.30},
    "noir":         {"agx": "very_high",   "lift": (0.98, 0.98, 0.98),   "gain": (1.0, 1.0, 1.0),    "sat": 0.10, "bloom": 0.10, "halation": 0.00, "vignette": 0.35},
    "vivid":        {"agx": "high",        "lift": (1.0, 1.0, 1.0),      "gain": (1.0, 1.0, 1.0),    "sat": 1.18, "bloom": 0.15, "halation": 0.05, "vignette": 0.10},
}


def _plan(preset, *, contrast, saturation, separation, effects, exposure_ev, agx=None, bloom=None):
    p = PRESETS[preset]
    halation = p["halation"] * effects
    return {
        "agxLookCandidates": AGX_LOOKS[agx or p["agx"]],
        "exposureEv": exposure_ev,
        "lift": p["lift"], "gamma": (1.0, 1.0, 1.0), "gain": p["gain"],
        "contrast": round((contrast - 1.0) * 50.0, 4),   # Bright/Contrast node units (eng)
        "saturation": p["sat"] * saturation,
        "subjectSat": separation ** 0.5, "backgroundSat": separation ** -0.5,  # ratio = separation (V-G01)
        "bloom": {"strength": p["bloom"] * effects if bloom is None else bloom, "threshold": 1.0, "size": 0.2},
        "halation": None if halation <= 0 else {"strength": halation, "threshold": 1.2, "size": 0.45,
                                                "tint": (1.0, 0.58, 0.38)},  # V-G05 orange near
        "vignette": p["vignette"] * effects,
    }


def plan_for(grade_ref):
    """Plan for a checked grade block reference {id, params}."""
    q = grade_ref["params"]
    if grade_ref["id"] == "neutral_film":
        return _plan("clean", contrast=q["contrast"], saturation=q["saturation"], separation=q["separation"],
                     effects=1.0, exposure_ev=0.0, agx=q["agxLook"], bloom=q["bloom"])
    if grade_ref["id"] == "mood_grade":
        return _plan(q["preset"], contrast=q["contrast"], saturation=q["saturation"],
                     separation=q["separation"], effects=q["effectsScale"], exposure_ev=q["exposureEv"])
    raise ValueError(f"no grade plan for {grade_ref['id']!r}")


def plan_changes_look(p):
    """True unless the plan is visually identity (every field the realiser applies)."""
    return not (p["agxLookCandidates"] == ["None"] and p["contrast"] == 0 and p["saturation"] == 1.0
                and p["bloom"]["strength"] == 0 and p["halation"] is None and p["vignette"] == 0
                and p["lift"] == (1.0, 1.0, 1.0) and p["gain"] == (1.0, 1.0, 1.0)
                and p["exposureEv"] == 0 and p["subjectSat"] == 1.0 and p["backgroundSat"] == 1.0)


def changes_look(grade_ref):
    """TIERS T2-08 script-level fallback: True unless the grade is visually identity."""
    return plan_changes_look(plan_for(grade_ref))
