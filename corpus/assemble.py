"""Drafts become records only here: validated, id == filename, never overwriting a record."""
import json

from corpus import CORPUS_DIR, REFS_DIR
from corpus.schema import validate

DRAFTS = CORPUS_DIR / "drafts"


def accept(draft, refs_dir=REFS_DIR):
    try:
        rec = json.loads(draft.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, [f"unreadable draft: {e}"]
    probs = validate(rec)
    if not probs and rec["id"] != draft.stem:
        probs = [f"id {rec['id']!r} must equal the file name {draft.stem!r}"]
    target = refs_dir / f"{draft.stem}.json"
    if not probs and target.exists():
        probs = [f"{target.name} exists; records are never overwritten by a draft"]
    if probs:
        return False, probs
    target.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    draft.unlink()
    return True, []
