"""User-turn messages. Job data comes from our code; user- or file-written text is fenced as
JSON-escaped data inside <untrusted_*> tags so it can never close or open a tag (spec §7)."""
import json

from engine.director.cards import profile_card
from engine.markers import _bad_chars, gltf_dir_to_placed, gltf_to_placed

FENCES = ("job", "untrusted_prompt", "untrusted_markers", "untrusted_model")
OWNED = ("schema", "seed", "direction", "prompt", "format", "markers", "realism")
NOT_REPLAYED = ("unsupported", "assumptions")
_MARKER_KEYS = ("id", "text", "timeS", "part")
MAX_CLIP_NAME = 80  # names come from the model file: bounded like any other untrusted text


def _safe(obj):
    s = json.dumps(obj, ensure_ascii=True, sort_keys=True)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _fence(tag, obj):
    return f"<{tag}>{_safe(obj)}</{tag}>"


def _r(v):
    return [round(x, 4) for x in v]


def _clip_name(v):
    return "".join(c for c in str(v or "") if not _bad_chars(c))[:MAX_CLIP_NAME]


def marker_hints(markers, profile):
    out = []
    for m in markers or []:
        h = {k: m[k] for k in _MARKER_KEYS if k in m}
        a = m["anchor"]
        gltf = a.get("space", "placed") == "gltf"
        anchor = {"space": "placed", "point": _r(gltf_to_placed(a["point"], profile) if gltf else a["point"])}
        if "normal" in a:
            anchor["normal"] = _r(gltf_dir_to_placed(a["normal"]) if gltf else a["normal"])
        h["anchor"] = anchor
        out.append(h)
    return out


def first_message(*, fmt, direction, profile, prompt, markers, detected):
    job = {"format": fmt,
           "direction": {"id": direction.id, "mood": direction.mood, "pace": direction.pace, "tone": direction.tone,
                         "world": getattr(direction, "world", "studio_cyc"),
                         "opener": getattr(direction, "opener", "low_hero_push")},   # never weather/wind
           "subject": profile_card(profile),
           "alreadyUnsupported": [{"capability": u["capability"], "source": u["source"]} for u in detected]}
    clips = [{"index": c["index"], "name": _clip_name(c.get("nameHint"))}
             for c in getattr(profile, "animationClips", None) or []]
    return "\n".join([_fence("job", job), _fence("untrusted_prompt", prompt or ""),
                      _fence("untrusted_markers", marker_hints(markers, profile)),
                      _fence("untrusted_model", {"animationClipNames": clips}),
                      "Write the scene script for this job."])


def repair_message(problems):
    return "\n".join([f"<checker_report>{_safe(problems)}</checker_report>",
                      "Your last script did not pass. Return the whole script again with these fixed; "
                      "keep everything else."])


def reroll_message(index, script, reasons, fmt):
    # Only the model's creative fields go back: owned fields, and the user-derived text in
    # unsupported[].ask and assumptions, stay out of the reroll turn.
    body = {k: v for k, v in script.items() if k not in OWNED + NOT_REPLAYED}
    return "\n".join([_fence("job", {"format": fmt}), f"<current_script>{_safe(body)}</current_script>",
                      f"<reroll>{_safe({'shot': index, 'reasons': list(reasons)})}</reroll>",
                      "Replace only that shot (same startS and endS). Return the whole script."])
