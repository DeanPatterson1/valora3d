"""Pure grade plans for neutral_film and mood_grade; engine/blender/grade.py realises them.
Preset numbers are (eng) starting values: calibrate via harness items T2-08, T3-08, T3-19, T3-20.

Task 61 finishes the render-studio compositor port with three params that default to 0 = off, so a script
without them gets exactly today's plan (no new keys): `halation` (> 0 sets the warm glare's strength,
replacing the preset's), `lensDistortion` (render-studio Lensdist; dispersion = # premium_dark round 6 (2026-09-25, owner-delegated look call), A/B on the courtyard hero, final blend, 256-512 spp,
# against the film (finished-reference 002/003: luma p5 .014, p50 .090, p95 .536, colourfulness .018):
# - AgX Base Contrast lifted the shadows (p5 .052) and Medium High held them (.025): Medium High stays, it is the
#   nearer to the film's crushed blacks (the night street read the same way: Base p50 .117, Medium High .082);
# - the gap was exposure and colour, and the film's is selective: its foliage is near grey while the caliper stays
#   yellow. A global gain .55 / sat .48 measured p5 .012, p95 .581, colourfulness .019 (was .025 / .696 / .056) but
#   turned the caliper khaki and the wheel close-up murky (real_r6 wheel sbs); gain 0.7 (-0.5 stop), subject sat
#   0.75 and the background a further bgSat 0.55 (0.41 in all) keep the car's colour and grey the set.
DISPERSION_PER_DISTORTION x
distortion, 0.00035 at 0.006, fit on) and `grain` (render-studio's ffmpeg GRAIN_FILTER as compositor white
noise: amplitude GRAIN_AMP x grain, a luma mask that keeps it in the shadows and mids, and a per-frame noise
W = seed + frame so frame N depends on the seed and the frame alone, METHODS R1)."""

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
    "premium_dark": {"agx": "medium_high", "lift": (0.985, 0.985, 0.99), "gain": (0.7, 0.7, 0.7),    "sat": 0.75, "bloom": 0.15, "halation": 0.10, "vignette": 0.25, "bgSat": 0.55},
    "warm_golden":  {"agx": "medium_high", "lift": (1.0, 0.995, 0.985),  "gain": (1.04, 1.0, 0.93),  "sat": 1.08, "bloom": 0.20, "halation": 0.20, "vignette": 0.15},
    "teal_night":   {"agx": "high",        "lift": (0.98, 1.0, 1.02),    "gain": (1.03, 1.0, 0.96),  "sat": 1.05, "bloom": 0.25, "halation": 0.25, "vignette": 0.30},
    "noir":         {"agx": "very_high",   "lift": (0.98, 0.98, 0.98),   "gain": (1.0, 1.0, 1.0),    "sat": 0.10, "bloom": 0.10, "halation": 0.00, "vignette": 0.35},
    "vivid":        {"agx": "high",        "lift": (1.0, 1.0, 1.0),      "gain": (1.0, 1.0, 1.0),    "sat": 1.18, "bloom": 0.15, "halation": 0.05, "vignette": 0.10},
}


DISPERSION_PER_DISTORTION = 0.00035 / 0.006   # render-studio rain_look.compositor
GRAIN_AMP = 0.1          # (eng) grain 0.5 ~ ffmpeg noise alls=13 (13/255 ~ 0.05 around mid grey)
GRAIN_MASK = (0.98, 1.35, 0.18)   # mask = clamp(a - b x luma, lo, a): ffmpeg lutyuv clip(250 - 1.35 val, 45, 250)
GRAIN_W_MOD = 100003     # keeps the noise W a small float (precision) while staying seed-distinct


BLOOM_THRESHOLD = 2.5    # render-studio rain_look.compositor: only true highlights bloom (was 1.0, realism audit #20)
# What a real camera adds to every frame whatever the grade (render-studio's rain film, rain_look.py:89-99 and
# pipeline.py:152): restrained fog-glow bloom, a faint warm halation, a slight barrel with edge dispersion and
# display-referred sensor grain. A script's own finish params only ever add to these (max), so plan_for (the
# script's grade, T2-08) is untouched; engine/blender/grade.realise applies camera_finished(plan).
CAMERA_FINISH = {"bloom": 0.03, "halation": 0.05, "lensDistortion": 0.006, "grain": 0.5}
# Round 5 (critique mat-v2 #5): a real lens's veiling glare is a 1-3 px halo on an LED, 2-4% of the highlight, so
# fog glow is held to BLOOM_MAX whatever the grade asks (paint highlights keep their shape), and the camera adds no
# chromatic aberration of its own (dispersion 0; a script's lensDistortion still brings its own).
BLOOM_MAX = 0.04
CAMERA_DISPERSION = 0.0


def camera_finished(plan, seed=0):
    """The grade plan as the camera records it: CAMERA_FINISH under the script's own finish."""
    from engine.compiler.context import block_seed
    c, out = CAMERA_FINISH, dict(plan)
    out["bloom"] = {**plan["bloom"], "strength": min(max(plan["bloom"]["strength"], c["bloom"]), BLOOM_MAX)}
    h = plan.get("halation")
    out["halation"] = h if h and h["strength"] >= c["halation"] else {
        "strength": c["halation"], "threshold": 1.2, "size": 0.45, "tint": (1.0, 0.58, 0.38)}
    lens = plan.get("lens")
    if not lens or lens["distortion"] < c["lensDistortion"]:
        d = c["lensDistortion"]
        out["lens"] = {"distortion": d, "dispersion": CAMERA_DISPERSION, "fit": True}
    g = plan.get("grain")
    if not g or g["amount"] < c["grain"]:
        a, b, lo = GRAIN_MASK
        out["grain"] = {"amount": c["grain"], "amplitude": GRAIN_AMP * c["grain"],
                        "seed": g["seed"] if g else block_seed(seed, "grade", "camera"), "mask": {"a": a, "b": b, "lo": lo}}
    return out


def grain_w(grain, frame):
    """The white-noise W for a frame: a fresh grain pattern every frame, the same one for the same frame."""
    return float(grain["seed"] % GRAIN_W_MOD) + float(frame)


def _finish(plan, q, bid, seed):
    """Add the Task 61 finishing specs only when their param is > 0 (absent key = off = today's plan)."""
    from engine.compiler.context import block_seed
    if q.get("halation", 0) > 0:
        plan["halation"] = {"strength": float(q["halation"]), "threshold": 1.2, "size": 0.45,
                            "tint": (1.0, 0.58, 0.38)}
    if q.get("lensDistortion", 0) > 0:
        d = float(q["lensDistortion"])
        plan["lens"] = {"distortion": d, "dispersion": d * DISPERSION_PER_DISTORTION, "fit": True}
    if q.get("grain", 0) > 0:
        a, b, lo = GRAIN_MASK
        plan["grain"] = {"amount": float(q["grain"]), "amplitude": GRAIN_AMP * float(q["grain"]),
                         "seed": block_seed(seed, "grade", bid), "mask": {"a": a, "b": b, "lo": lo}}
    return plan


def _plan(preset, *, contrast, saturation, separation, effects, exposure_ev, agx=None, bloom=None):
    p = PRESETS[preset]
    halation = p["halation"] * effects
    return {
        "agxLookCandidates": AGX_LOOKS[agx or p["agx"]],
        "exposureEv": exposure_ev,
        "lift": p["lift"], "gamma": (1.0, 1.0, 1.0), "gain": p["gain"],
        "contrast": round((contrast - 1.0) * 50.0, 4),   # Bright/Contrast node units (eng)
        "saturation": p["sat"] * saturation,
        "subjectSat": separation ** 0.5, "backgroundSat": separation ** -0.5 * p.get("bgSat", 1.0),  # V-G01
        "bloom": {"strength": p["bloom"] * effects if bloom is None else bloom, "threshold": BLOOM_THRESHOLD,
                  "size": 0.2},
        "halation": None if halation <= 0 else {"strength": halation, "threshold": 1.2, "size": 0.45,
                                                "tint": (1.0, 0.58, 0.38)},  # V-G05 orange near
        "vignette": p["vignette"] * effects,
    }


def plan_for(grade_ref, seed=0):
    """Plan for a checked grade block reference {id, params}; `seed` is the script seed (grain)."""
    q = grade_ref["params"]
    if grade_ref["id"] == "neutral_film":
        return _finish(_plan("clean", contrast=q["contrast"], saturation=q["saturation"], separation=q["separation"],
                             effects=1.0, exposure_ev=0.0, agx=q["agxLook"], bloom=q["bloom"]),
                       {"grain": q.get("grain", 0)}, "neutral_film", seed)
    if grade_ref["id"] == "mood_grade":
        return _finish(_plan(q["preset"], contrast=q["contrast"], saturation=q["saturation"],
                             separation=q["separation"], effects=q["effectsScale"], exposure_ev=q["exposureEv"]),
                       q, "mood_grade", seed)
    raise ValueError(f"no grade plan for {grade_ref['id']!r}")


SUN_TIMES = ("dawn", "golden", "dusk")   # a world lit by a low sun: its sky's warm/cool IS the story


def keep_sun_colour(plan, script, params):
    """Round 8 (owner's r7 grade: "a subtle sunset sky, not an orange filter"): premium_dark's further set greying
    (bgSat, fit to the rain film's grey foliage) took a golden field's warm horizon and cooler upper sky down to one
    grey. Under a low sun the background keeps the separation's own ratio; nothing else in the plan changes."""
    tod = ((script.get("world") or {}).get("params") or {}).get("timeOfDay")
    bg = PRESETS.get(params.get("preset"), {}).get("bgSat")
    if tod not in SUN_TIMES or bg is None:
        return plan
    return {**plan, "backgroundSat": plan["backgroundSat"] / bg}


def plan_changes_look(p):
    """True unless the plan is visually identity (every field the realiser applies)."""
    return not (p["agxLookCandidates"] == ["None"] and p["contrast"] == 0 and p["saturation"] == 1.0
                and p["bloom"]["strength"] == 0 and p["halation"] is None and p["vignette"] == 0
                and p["lift"] == (1.0, 1.0, 1.0) and p["gain"] == (1.0, 1.0, 1.0)
                and p["exposureEv"] == 0 and p["subjectSat"] == 1.0 and p["backgroundSat"] == 1.0
                and not p.get("lens") and not p.get("grain"))


def changes_look(grade_ref):
    """TIERS T2-08 script-level fallback: True unless the grade is visually identity."""
    return plan_changes_look(plan_for(grade_ref))
