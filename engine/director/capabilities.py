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
_NEG_WORD = re.compile(r"\b(?:no|without|not(?!\s+only\b)|don['’]?t|never|minus|avoid(?:ing)?|zero|less|skip)\b",
                       re.I)
_NEG_REACH = re.compile(r"[\s-]+(?:[\w'’-]+\s+){0,4}")  # a negator reaches at most 4 words forward
_NEG_AFTER = re.compile(r"[\s-]*free\b", re.I)  # "rain-free", "smoke free"
# Punctuation must not hide a negation ('no "moody"', 'no (moody)', 'no—moody'). Length-preserving, so
# match offsets still hold: quotes and opening brackets become spaces; a closed bracket group is its own
# scope (_drop_closed_groups: '(no rain) smoke' stays positive, 'no (very) moody' stays negated); an
# unmatched closing bracket or a SPACED dash ends the clause ('no text — music'); an unspaced Unicode dash
# is a hyphen.
_QUOTES = re.compile(r"[\"“”„‟«»‹›`]|(?<!\w)['‘’]|['‘’](?!\w)")
_OPEN, _CLOSE = re.compile(r"[(\[{<]"), re.compile(r"[)\]}>]")
_DASHES = "‐‑‒–—―−⸺⸻﹘﹣－"
_SPACED_DASH = re.compile(rf"(?<=\s)[{_DASHES}]+(?=\s)")
_DASH = re.compile(rf"[{_DASHES}]")


def _clean(text, n=MAX_ASK):
    return "".join(c for c in str(text) if not _bad_chars(c)).strip()[:n]


def _neg_text(text):
    """text, same length, with quotes, brackets and Unicode dashes normalised for the negation reader."""
    text = _CLOSE.sub(";", _OPEN.sub(" ", _QUOTES.sub(" ", text)))
    text = _SPACED_DASH.sub(lambda x: ";" * len(x.group(0)), text)
    return _DASH.sub("-", text)


def _drop_closed_groups(before):
    """`before` with every bracket group that closes before the match collapsed to one space: its words are
    their own scope, so a negator inside '(no rush) moody' does not reach 'moody', and one outside
    'no (very) moody' still does. A group still open at the match encloses it ('no (moody'), so it stays;
    an unmatched closing bracket is kept and ends the clause."""
    out, opens = [], []   # opens: index in `out` of each still-open bracket
    for ch in before:
        if _OPEN.match(ch):
            opens.append(len(out))
        elif _CLOSE.match(ch) and opens:
            del out[opens.pop():]
            out.append(" ")
            continue
        out.append(ch)
    return "".join(out)


def _negated(text, m):
    """True when the match is negated inside its own clause. Every negator that reaches it (at most 4
    words before it) counts, plus a trailing '-free'. An even count is positive: 'not not moody' and
    'not without rain' ask for the thing."""
    norm = _neg_text(text)
    before = _neg_text(_drop_closed_groups(text[:m.start()]))
    ends = [e.end() for e in _CLAUSE_END.finditer(before)]
    clause = (before[ends[-1]:] if ends else before)[-60:]
    n = sum(1 for w in _NEG_WORD.finditer(clause) if _NEG_REACH.fullmatch(clause, w.end()))
    return (n + (1 if _NEG_AFTER.match(norm, m.end()) else 0)) % 2 == 1


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


GENERIC_NOTE = "This isn't available yet, so it was left out."
WORLD_NOTE = "That needs a different setting than this video uses, so it was left out."
PROFILE_NOTE = "That doesn't suit this model, so it was left out."
PLACEMENT_NOTE = "That motion needs the subject on the ground, so it rests there instead of floating."
# checker error code -> the vocabulary note key that explains it (Task 85; PHASING §3.6)
CODE_NOTE = {"effect_needs_world": "worldNote", "path_through_world": "worldNote", "camera_needs_motion": "worldNote",
             "effect_needs_profile": "profileNote", "motion_needs_profile": "profileNote",
             "motion_needs_ground": "placementNote", "effect_needs_source": "sourceNote"}
_FALLBACK_NOTE = {"worldNote": WORLD_NOTE, "profileNote": PROFILE_NOTE, "sourceNote": WORLD_NOTE,
                  "placementNote": PLACEMENT_NOTE}
# a placement the pipeline changed (kind "placement") -> the asks it served (review chunk7 #6)
PLACEMENT_CAPS = {"float": {"motion.float"}}


def blocked_note(tag, key):
    """The vocabulary's note for an ask whose block exists but is blocked (key: worldNote | profileNote |
    sourceNote), else a plain generic line. Never the "isn't available yet" note: the block exists."""
    return VOCAB.get(tag, {}).get(key) or _FALLBACK_NOTE[key]


def _providers(tag, catalog):
    """(kind, manifest) of every menu block that delivers `tag` (selectable only: what the director can use)."""
    from engine.director.menu import KIND_ORDER
    out = []
    for k in KIND_ORDER:
        for b in catalog.selectable_ids(k):
            m = catalog.get(k, b) or {}
            if tag in m.get("capabilities", []):
                out.append((k, m))
    return out


def _note(tag, catalog, profile):
    clips = getattr(profile, "animationClips", None) or []
    if tag == CLIP_TAG and clips and not clips_current(clips):   # measured before the clip map: re-ingest
        return STALE_NOTE
    provs = _providers(tag, catalog) if tag != CLIP_TAG else []
    if provs and profile is not None and not any(catalog.applies(m, profile) for _, m in provs):
        return blocked_note(tag, "profileNote")     # the block exists; this model lacks what it needs
    return NOTES.get(tag, GENERIC_NOTE)


def _motion_flags(script, catalog):
    from engine.physics.applies import motion_flags
    try:
        return {k for k, v in motion_flags(script, catalog).items() if v}
    except (KeyError, TypeError, AttributeError, ValueError):
        m = catalog.get("motion", ((script.get("subject") or {}).get("motion") or {}).get("id", "static")) or {}
        return {k for k, v in (m.get("subjectMotion") or {}).items() if v}


def _blocked_by(kind, m, world, script, catalog):
    """True when this script's world (or its subject's motion) keeps block `m` out, by the checker's own rules."""
    if kind == "effect":
        from engine.weather_rules import _needs_world
        return bool(_needs_world((m.get("physics") or {}).get("requiresWorld") or {}, world))
    if kind == "motion":
        return bool(m.get("vehicle")) and float(world.get("driveLaneM", 0.0)) <= 0.0
    if kind == "camera":
        need = set(m.get("requiresMotion") or [])
        return bool(need - _motion_flags(script, catalog))
    if kind == "lighting":
        from engine.lighting.pairing import allowed_lighting
        pairs = allowed_lighting(world)
        return bool(pairs) and m["id"] not in pairs
    return False


def world_blocked(tag, script, catalog, profile):
    """The world-blocked note when blocks deliver `tag` for this profile but every one of them is kept out by
    the script's world or its subject's motion (rain in the studio, a drive without a road, a tracking camera
    on a still subject); else None."""
    if not isinstance(script, dict):
        return None
    provs = [(k, m) for k, m in _providers(tag, catalog) if profile is None or catalog.applies(m, profile)]
    if not provs:
        return None
    world = catalog.get("world", (script.get("world") or {}).get("id")) or {}
    if all(_blocked_by(k, m, world, script, catalog) for k, m in provs):
        return blocked_note(tag, "worldNote")
    return None


def unsupported(asks, catalog, profile, script=None):
    """One entry per phrase ("an explosion" once, though it names two tags), capped at the script's
    MAX_UNSUPPORTED: the overflow becomes one last entry, "…and N more things". With a script, an ask the
    catalog can deliver but the script's world blocks is reported too, with the world-blocked note."""
    have = catalog.capabilities(profile)
    out, seen, seen_ask = [], set(), set()
    for a in asks:
        tag = a["capability"]
        if tag in seen or a["ask"].lower() in seen_ask:
            continue
        note = world_blocked(tag, script, catalog, profile) if tag in have and script is not None else None
        if tag in have and note is None:
            continue
        seen.add(tag)
        seen_ask.add(a["ask"].lower())
        out.append({"ask": a["ask"], "capability": tag, "note": note or _note(tag, catalog, profile),
                    "source": a["source"]})
    return _fold(out)


def _script_refs(script):
    """(kind, block ref) for every block the script uses."""
    out = [(k, script.get(k)) for k in ("world", "lighting", "grade", "edit")]
    out.append(("field", script.get("wind")))
    out.append(("motion", (script.get("subject") or {}).get("motion")))
    out += [("effect", e) for e in script.get("effects") or []]
    out += [("camera", sh.get("camera")) for sh in script.get("shots") or [] if isinstance(sh, dict)]
    return [(k, r["id"]) for k, r in out if isinstance(r, dict) and isinstance(r.get("id"), str)]


def delivers(script, tag, catalog):
    """Some block in the script delivers `tag`."""
    return any(tag in (catalog.get(k, b) or {}).get("capabilities", []) for k, b in _script_refs(script))


def _partial(u, script):
    p = VOCAB.get(u["capability"], {}).get("partialNote")
    if p and any(isinstance(e, dict) and e.get("id") == p["effect"] for e in script.get("effects") or []):
        return p["note"]
    return u["note"]


def finish_unsupported(script, asks, catalog, profile, extra=()):
    """The delivered script's honest list (Task 85): `extra` entries (blocks the pipeline took out of a reply,
    blocked_entries) and every deliverable ask this script's world blocks are added with their blocked note
    (never a silent drop), and partial-support notes follow what the script really has ("...the subject has
    still droplets instead"). Assumption lines follow the notes. Mutates and returns `script`."""
    have = catalog.capabilities(profile)
    cur = list(script.get("unsupported") or [])
    notes = list(script.get("assumptions") or [])
    tags = {u["capability"] for u in cur}
    asked = {u["ask"].lower() for u in cur}
    for u in extra:
        if u["capability"] not in tags and u["ask"].lower() not in asked:
            cur.append(dict(u))
            tags.add(u["capability"])
            asked.add(u["ask"].lower())
    for a in asks:
        tag = a["capability"]
        if tag not in have or tag in tags or a["ask"].lower() in asked or delivers(script, tag, catalog):
            continue
        note = world_blocked(tag, script, catalog, profile)
        if note:
            cur.append({"ask": a["ask"], "capability": tag, "note": note, "source": a["source"]})
            tags.add(tag)
            asked.add(a["ask"].lower())
    for u in cur:
        new = _partial(u, script)
        if new != u["note"]:
            notes = [new if x == u["note"] else x for x in notes]
            u["note"] = new
    cur = _fold(cur)
    for u in cur:
        if u["note"] not in notes:
            notes.append(u["note"])
    if cur:
        script["unsupported"] = cur
        script["assumptions"] = notes
    return script


def blocked_entries(removed, asks, catalog):
    """unsupported entries for the blocks the pipeline took out of a reply: [(kind, id, code)] -> one entry per
    ask whose capability the removed block delivers, with the note for the code (CODE_NOTE)."""
    out, seen = [], set()
    for kind, bid, code in removed:
        caps = PLACEMENT_CAPS.get(bid, set()) if kind == "placement" else             set((catalog.get(kind, bid) or {}).get("capabilities", []))
        for a in asks:
            if a["capability"] in caps and a["capability"] not in seen:
                seen.add(a["capability"])
                out.append({"ask": a["ask"], "capability": a["capability"],
                            "note": blocked_note(a["capability"], CODE_NOTE.get(code, "worldNote")),
                            "source": a["source"]})
    return out


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
