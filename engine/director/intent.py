"""Format pins read from the prompt, and the job's format (spec D5: 9:16, 8-12 s when the prompt
says nothing about format). Format is owned by the pipeline; the LLM never writes it."""
import re

from engine.script import DURATION_RANGE

DEFAULT_ASPECT, DEFAULT_FPS = "9:16", 24   # 24 fps (2026-09-29 render-cost lane): 20% fewer frames per second of clip; a prompt can pin 25/30/60
DEFAULT_DURATION_S = 10  # D5 allows 8-12 s; spec §4.2's example uses 10. Phase 4's dice may vary it.
ASPECT_WORDS = (("9:16", ("9:16", "vertical", "portrait", "reel", "reels", "tiktok", "shorts", "story", "stories")),
                ("16:9", ("16:9", "landscape", "widescreen", "horizontal")),
                ("1:1", ("1:1", "square")),
                ("4:5", ("4:5", "feed post", "instagram post")))
_DUR = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)[\s-]*(?:s|sec|secs|second|seconds)\b", re.I)
_FPS = re.compile(r"\b(24|25|30|60)\s*fps\b", re.I)
_WORD = re.compile(r"[a-z0-9']+")


def _has(text, word):
    return re.search(r"(?<![\w:])" + re.escape(word) + r"(?![\w:])", text) is not None


def read_pins(prompt):
    t = (prompt or "").lower()
    pins = {}
    for aspect, words in ASPECT_WORDS:
        if any(_has(t, w) for w in words):
            pins["aspect"] = aspect
            break
    m = _DUR.search(t)
    if m:
        pins["durationS"] = float(m.group(1))
    m = _FPS.search(t)
    if m:
        pins["fps"] = int(m.group(1))
    return pins


def make_format(pins, seed=None, duration=None):
    """A prompt duration pin beats `duration` (explicit, liked or rolled by the job), which beats the
    10 s default. seed is kept for callers; the job rolls the duration (dice.roll_duration)."""
    fps = pins.get("fps", DEFAULT_FPS)
    d = pins.get("durationS", DEFAULT_DURATION_S if duration is None else duration)
    d = min(max(d, DURATION_RANGE[0]), DURATION_RANGE[1])
    d = round(d * fps) / fps
    return {"aspect": pins.get("aspect", DEFAULT_ASPECT), "durationS": int(d) if d == int(d) else d, "fps": fps}


def format_notes(pins, fmt):
    if "aspect" not in pins and "durationS" not in pins:
        return [f"no format given -> {fmt['aspect']}, {fmt['durationS']:g} s"]
    out = []
    if "aspect" not in pins:
        out.append(f"no aspect given -> {fmt['aspect']}")
    if "durationS" in pins and abs(pins["durationS"] - fmt["durationS"]) > 0.5 / fmt["fps"]:
        lo, hi = DURATION_RANGE
        side = "longer than the" if pins["durationS"] > hi else "shorter than the"
        lim = hi if pins["durationS"] > hi else lo
        out.append(f"{pins['durationS']:g} s is {side} {lim} s {'maximum' if lim == hi else 'minimum'} "
                   f"-> {fmt['durationS']:g} s")
    return out


def is_vague(prompt):
    return len(_WORD.findall((prompt or "").lower())) <= 4
