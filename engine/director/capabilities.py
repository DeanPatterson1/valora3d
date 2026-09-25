"""What a prompt can ask for, and what the catalog can deliver (coordinator addition 2026-09-24).

Every ask whose capability no selectable block provides is returned to the user in the script's
`unsupported` list with a plain note, and is never silently dropped. Detection here is deterministic
(phrases); the LLM may add asks the phrases miss (merge_llm), but it can never remove one."""
import json
import re
from pathlib import Path

from engine.clips import CLIP_TAG, STALE_NOTE, choose_clip, clips_current, in_place_line, resolve_mode
from engine.markers import _bad_chars
from engine.script import MAX_UNSUPPORTED

VOCAB_FILE = Path(__file__).with_name("vocabulary.json")
MAX_ASK = 60


def load_vocabulary(path=VOCAB_FILE):
    """{tag: {phrases: [regex, ...], note: str | None}}. Data, so new blocks (physics, worlds...) add
    their tags and phrases here without touching director code (owner 2026-09-24)."""
    return json.loads(path.read_text(encoding="utf-8"))["tags"]


VOCAB = load_vocabulary()
KNOWN_TAGS = frozenset(VOCAB)
BLOCK_ONLY_TAGS = frozenset(tag for tag, v in VOCAB.items() if not v["phrases"])
NOTES = {tag: v["note"] for tag, v in VOCAB.items() if v.get("note")}
# Inflections (rains, storms, sunsets, walked, poured) come from one suffix group, not per-phrase lists.
_SUFFIX = r"(?:s|es|ed)?"
_RX = [(tag, re.compile(r"\b(?:" + "|".join(v["phrases"]) + r")" + _SUFFIX + r"\b", re.I),
        [re.compile(x, re.I) for x in v.get("except", [])]) for tag, v in VOCAB.items() if v["phrases"]]
# A negation reaches forward only inside its own clause: "no text, just music" still asks for music.
_CLAUSE_END = re.compile(r"[,;.!?:]|\b(?:but|and|just|then|plus)\b", re.I)
_NEG = re.compile(r"\b(?:no|without|not(?!\s+only\b)|don['’]?t|never|minus|avoid(?:ing)?|zero|less|skip)"
                  r"[\s-]+(?:[\w'’-]+\s+){0,4}$", re.I)
_NEG_AFTER = re.compile(r"[\s-]*free\b", re.I)  # "rain-free", "smoke free"


def _clean(text, n=MAX_ASK):
    return "".join(c for c in str(text) if not _bad_chars(c)).strip()[:n]


def _negated(text, m):
    before = text[:m.start()]
    ends = [e.end() for e in _CLAUSE_END.finditer(before)]
    clause = before[ends[-1]:] if ends else before
    return bool(_NEG.search(clause[-60:]) or _NEG_AFTER.match(text, m.end()))


def detect(text, source="prompt"):
    """Asks in `text`, in reading order, one per capability. 'no rain' / 'without text' / 'rain-free'
    are not asks; 'water-resistant' is not water (a tag's `except` phrases)."""
    text = text or ""
    found = []
    for tag, rx, excepts in _RX:
        spans = [(e.start(), e.end()) for x in excepts for e in x.finditer(text)]
        for m in rx.finditer(text):
            if any(s < m.end() and m.start() < e for s, e in spans) or _negated(text, m):
                continue
            found.append((m.start(), {"ask": _clean(m.group(0)), "capability": tag, "source": source}))
            break
    return [a for _, a in sorted(found, key=lambda x: x[0])]


def _note(tag, catalog, profile):
    clips = getattr(profile, "animationClips", None) or []
    if tag == CLIP_TAG and clips and not clips_current(clips):   # measured before the clip map: re-ingest
        return STALE_NOTE
    return NOTES.get(tag, "This isn't available yet, so it was left out.")


def unsupported(asks, catalog, profile):
    """One entry per phrase ("an explosion" once, though it names two tags), capped at the script's
    MAX_UNSUPPORTED: the overflow becomes one last entry, "…and N more things"."""
    have = catalog.capabilities(profile)
    out, seen, seen_ask = [], set(), set()
    for a in asks:
        if a["capability"] in have or a["capability"] in seen or a["ask"].lower() in seen_ask:
            continue
        seen.add(a["capability"])
        seen_ask.add(a["ask"].lower())
        out.append({"ask": a["ask"], "capability": a["capability"],
                    "note": _note(a["capability"], catalog, profile), "source": a["source"]})
    return _fold(out)


def _fold(out):
    """Cap at the script's MAX_UNSUPPORTED: the overflow becomes one last entry, "…and N more things"."""
    if len(out) <= MAX_UNSUPPORTED:
        return out
    rest = out[MAX_UNSUPPORTED - 1:]
    note = "These aren't available yet either, so they were left out: " + ", ".join(r["ask"] for r in rest)
    return out[:MAX_UNSUPPORTED - 1] + [{"ask": f"…and {len(rest)} more things", "capability": "other",
                                         "note": _clean(note, 160), "source": rest[0]["source"]}]


# The model's ask is shown to the user and may quote prompt or marker text (untrusted). Cap it below
# the eval's 24-char hostile-echo window (harness ECHO_CHARS) and never splice it into a note.
MAX_LLM_ASK = 23
OTHER_NOTE = "Something you asked for isn't available yet, so it was left out."
MAX_LLM_OTHER = 3  # (eng) the model's own 'other' asks: a few, so a hostile prompt cannot flood the list


def _short(ask, n=MAX_LLM_ASK):
    if len(ask) <= n:
        return ask
    cut = ask[:n + 1].rsplit(" ", 1)[0] if " " in ask[:n + 1] else ask[:n]
    return cut[:n].strip()


def merge_llm(detected, llm_items, catalog, profile):
    """Deterministic detections first and always kept; then the model's own additions, if they name a
    capability nothing provides (or 'other'). The model can add asks; it can never remove one."""
    have = catalog.capabilities(profile)
    out = list(detected)
    seen = {u["capability"] for u in out if u["capability"] != "other"}
    seen_ask = {u["ask"].lower() for u in out}
    n_other = 0
    for it in llm_items if isinstance(llm_items, list) else []:
        if not isinstance(it, dict):
            continue
        ask, tag = _short(_clean(it.get("ask", ""))), str(it.get("capability", "other"))
        tag = tag if tag in KNOWN_TAGS else "other"
        if not ask or tag in have or tag in seen or ask.lower() in seen_ask:
            continue
        if tag == "other" and n_other >= MAX_LLM_OTHER:
            continue
        n_other += tag == "other"
        note = OTHER_NOTE if tag == "other" else _note(tag, catalog, profile)
        out.append({"ask": ask, "capability": tag, "note": note[:160], "source": "director"})
        seen_ask.add(ask.lower())
        if tag != "other":
            seen.add(tag)
    return _fold(out)


def wants_clip(asks, catalog, profile):
    """A movement ask the model can honour with its own clip. Once supported it is not in `unsupported`,
    so the script must actually play a clip (never silently drop a supported ask, review 2026-09-25)."""
    return any(a["capability"] == CLIP_TAG for a in asks) and CLIP_TAG in catalog.capabilities(profile)


def play_clip_ref(asks, profile):
    """play_clip on the clip the movement asks name (engine.clips.choose_clip), else the longest clip."""
    return {"id": "play_clip", "params": {"clip": choose_clip(asks, getattr(profile, "animationClips", []))}}


def clip_line(profile, i):
    """The assumption line for a system-chosen play_clip: which clip, and how it fills the video."""
    clips = getattr(profile, "animationClips", [])
    seamless = clips[i].get("seamless") if 0 <= i < len(clips) else None
    how = ("played forwards then backwards, since its last pose does not match its first"
           if resolve_mode("auto", seamless) == "pingpong" else "looped")
    line = f"the prompt asked for movement -> playing the model's animation clip {i}, {how}"
    if in_place_line(clips, {"id": "play_clip", "params": {"clip": i}}):
        line += " and plays in place (it walks forward; a loop would jump back each cycle)"
    return line


def assumption_lines(items):
    lines = []
    for u in items:
        if u["note"] not in lines:
            lines.append(u["note"])
    return lines
