"""Drafts become records only here: validated, id == filename, never overwriting a record, the clip
file present for a downloaded record, and at most MAX_IN_PLAYER_PER_DAY in-player studies a day."""
import json
from pathlib import Path

from corpus import CORPUS_DIR, LOCAL_DIR, REFS_DIR, ROOT
from corpus.schema import OWNER_FILE_PREFIX, validate

DRAFTS = CORPUS_DIR / "drafts"
MAX_IN_PLAYER_PER_DAY = 20   # extract.md: at most 20 clips a day in the owner's Chrome


def _file_problem(rec, local_dir, root):
    src = rec["source"]
    if src["kind"] == "owner":
        rel = src.get("file") or f"{OWNER_FILE_PREFIX}clips/{rec['id']}.mp4"
        if not (Path(root) / rel).is_file():
            return f"source: the owner clip {rel} is not there"
    elif src["kind"] in ("stock", "link") and src.get("downloaded"):
        base = Path(local_dir).resolve()
        f = (base / src["localFile"]).resolve()
        if not f.is_relative_to(base) or not f.is_file():
            return f"source.localFile: {src['localFile']} is not a file under {local_dir}"
    return None


def _in_player_count(refs_dir, day):
    n = 0
    for p in Path(refs_dir).glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        n += r.get("method") == "in_player" and (r.get("source") or {}).get("studiedAt") == day
    return n


def accept(draft, refs_dir=REFS_DIR, local_dir=LOCAL_DIR, root=ROOT):
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
    if not probs:
        fp = _file_problem(rec, local_dir, root)
        probs = [fp] if fp else []
    if not probs and rec["method"] == "in_player":
        day = rec["source"]["studiedAt"]
        if _in_player_count(refs_dir, day) >= MAX_IN_PLAYER_PER_DAY:
            probs = [f"{MAX_IN_PLAYER_PER_DAY} in_player records already studied on {day}; study the rest another day"]
    if probs:
        return False, probs
    target.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    draft.unlink()
    return True, []
