"""What a prompt can ask for, and what the catalog can deliver (coordinator addition 2026-09-24).

Every ask whose capability no selectable block provides is returned to the user in the script's
`unsupported` list with a plain note, and is never silently dropped. Detection here is deterministic
(phrases); the LLM may add asks the phrases miss (merge_llm), but it can never remove one."""
import json
import re
from pathlib import Path

from engine.markers import _bad_chars

VOCAB_FILE = Path(__file__).with_name("vocabulary.json")
MAX_ASK = 60
NO_CLIPS_NOTE = "This model has no animation of its own, so it is shown still."


def load_vocabulary(path=VOCAB_FILE):
    """{tag: {phrases: [regex, ...], note: str | None}}. Data, so new blocks (physics, worlds...) add
    their tags and phrases here without touching director code (owner 2026-09-24)."""
    return json.loads(path.read_text(encoding="utf-8"))["tags"]


VOCAB = load_vocabulary()
KNOWN_TAGS = frozenset(VOCAB)
BLOCK_ONLY_TAGS = frozenset(tag for tag, v in VOCAB.items() if not v["phrases"])
NOTES = {tag: v["note"] for tag, v in VOCAB.items() if v.get("note")}
_RX = [(tag, re.compile(r"\b(?:" + "|".join(v["phrases"]) + r")\b", re.I)) for tag, v in VOCAB.items() if v["phrases"]]
_NEG = re.compile(r"\b(?:no|without|not|don'?t|never|minus)\s+(?:[\w'-]+[\s,]+){0,4}$", re.I)


def _clean(text, n=MAX_ASK):
    return "".join(c for c in str(text) if not _bad_chars(c)).strip()[:n]


def detect(text, source="prompt"):
    """Asks in `text`, in reading order, one per capability. 'no rain' / 'without text' are not asks."""
    text = text or ""
    found = []
    for tag, rx in _RX:
        for m in rx.finditer(text):
            if _NEG.search(text[max(0, m.start() - 40):m.start()]):
                continue
            found.append((m.start(), {"ask": _clean(m.group(0)), "capability": tag, "source": source}))
            break
    return [a for _, a in sorted(found, key=lambda x: x[0])]


def _note(tag, catalog, profile):
    if tag == "motion.character_clip" and tag in catalog.capabilities(None):
        return NO_CLIPS_NOTE  # the block exists; this model has nothing to play
    return NOTES.get(tag, "This isn't available yet, so it was left out.")


def unsupported(asks, catalog, profile):
    have = catalog.capabilities(profile)
    out, seen = [], set()
    for a in asks:
        if a["capability"] in have or a["capability"] in seen:
            continue
        seen.add(a["capability"])
        out.append({"ask": a["ask"], "capability": a["capability"],
                    "note": _note(a["capability"], catalog, profile), "source": a["source"]})
    return out


def merge_llm(detected, llm_items, catalog, profile):
    """Deterministic detections first and always kept; then the model's own additions, if they name a
    capability nothing provides (or 'other'). The model can add asks; it can never remove one."""
    have = catalog.capabilities(profile)
    out = list(detected)
    seen = {u["capability"] for u in out if u["capability"] != "other"}
    seen_ask = {u["ask"].lower() for u in out}
    for it in llm_items if isinstance(llm_items, list) else []:
        if not isinstance(it, dict):
            continue
        ask, tag = _clean(it.get("ask", "")), str(it.get("capability", "other"))
        tag = tag if tag in KNOWN_TAGS else "other"
        if not ask or tag in have or tag in seen or ask.lower() in seen_ask:
            continue
        note = (f"“{ask}” isn't available yet, so it was left out." if tag == "other"
                else _note(tag, catalog, profile))
        out.append({"ask": ask, "capability": tag, "note": note[:160], "source": "director"})
        seen_ask.add(ask.lower())
        if tag != "other":
            seen.add(tag)
    return out[:12]


def assumption_lines(items):
    lines = []
    for u in items:
        if u["note"] not in lines:
            lines.append(u["note"])
    return lines
