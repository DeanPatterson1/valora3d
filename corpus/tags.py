"""Tag free-text notes ("neverThoughtOf", shot notes) into a fixed taxonomy with Laya (spec §9a).
The counts feed the catalog backlog ("things we never thought of"). Laya answers `choice` questions
only; a confidence below REVIEW_BELOW sends the row to Claude for review."""
import json

from corpus import CORPUS_DIR

NOTE_TAGS = CORPUS_DIR / "note-tags.json"
REVIEW_BELOW = 0.5
TAGS = {
    "world": "the place or environment: set, landscape, city, weather, time of day",
    "camera": "camera placement or movement, lens, framing, focus",
    "lighting": "lights, reflections, shadows, glow",
    "surface": "materials or surface state: dust, droplets, frost, wear, texture",
    "simulation": "physics: liquid, particles, cloth, smoke, falling or breaking objects",
    "secondary_subject": "another living thing or object in the scene: animal, traffic, people",
    "edit_format": "editing, cuts, transitions, split screen, rotated or blurred layouts",
    "overlay_text": "text, captions, logos, graphics drawn over the video",
    "imperfection": "camera flaws on purpose: shake, blur, flare, distortion, grain",
}


def load_laya():
    import truststore  # Norton intercepts TLS; the HF weight download fails without this
    truststore.inject_into_ssl()
    import laya
    return laya.load()


def notes_of(rec):
    out = [(rec["id"], "neverThoughtOf", n) for n in rec.get("neverThoughtOf", []) if n.strip()]
    out += [(rec["id"], f"shots[{i}].notes", sh["notes"]) for i, sh in enumerate(rec.get("shots", []))
            if sh.get("notes", "").strip()]
    return out


def _answer(result):
    # Laya 0.3.6 returns a plain dict (probed 2026-09-24):
    # {'model': 'laya-rl-agent', 'answers': {'tag': {'type': 'choice', 'choice': 'secondary subject',
    #  'probabilities': {...}, 'confidence': 0.2537, 'action': {...}}}, 'usage': {...}}
    # The attribute branch is kept in case a later Laya returns objects.
    ans = result["answers"]["tag"] if isinstance(result, dict) else result.answers.tag
    get = (lambda k: ans.get(k)) if isinstance(ans, dict) else (lambda k: getattr(ans, k, None))  # noqa: E731
    return get("choice"), float(get("confidence") or 0.0)


def tag_notes(records, classifier):
    q = {"tag": {"type": "choice", "criteria": TAGS,
                 "instructions": "Which ONE area of video craft is `note` about?"}}
    rows = []
    for rec in records:
        for ref, field, note in notes_of(rec):
            choice, conf = _answer(classifier.predict({"note": note}, q))
            ok = choice in TAGS
            rows.append({"ref": ref, "field": field, "note": note, "tag": choice if ok else None,
                         "confidence": round(conf, 3), "needsReview": (not ok) or conf < REVIEW_BELOW})
    return rows


def run(records, out=NOTE_TAGS):
    rows = tag_notes(records, load_laya())
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return rows
