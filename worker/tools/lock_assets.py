"""Write worker/assets-lock.json: where CI downloads each pinned library file from.

Every file in engine/assets/manifest.json is a CC0 Poly Haven asset. Some were renamed locally, so the match is by
content (Poly Haven publishes an md5 per file), not by name. Run it on a machine that has assets-in/library after the
manifest changes; CI then fetches from Poly Haven (worker/tools/fetch_assets.py) and checks every sha256 against the
manifest, so no library file ever has to be uploaded from a workstation.

    py worker/tools/lock_assets.py [--library ../Rendering/assets-in/library]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "engine" / "assets" / "manifest.json"
LOCK = REPO / "worker" / "assets-lock.json"
API = "https://api.polyhaven.com/files/{}"
UA = {"User-Agent": "valora3d-worker-build"}


def manifest_digest() -> str:
    """sha256 of the manifest with LF line endings, so a Windows (CRLF) checkout and CI agree."""
    return hashlib.sha256(MANIFEST.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _files(node, acc):
    if isinstance(node, dict):
        if isinstance(node.get("url"), str) and "md5" in node:
            acc.append(node)
        for v in node.values():
            _files(v, acc)
    elif isinstance(node, list):
        for v in node:
            _files(v, acc)
    return acc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", default=str(REPO.parent / "Rendering" / "assets-in" / "library"))
    args = ap.parse_args()
    library = Path(args.library)
    assets = json.loads(MANIFEST.read_text(encoding="utf-8"))["assets"]
    by_md5: dict[str, dict[str, str]] = {}
    lock, missing = {}, []
    for key in sorted(assets):
        a = assets[key]
        asset_id = a["source"].rstrip("/").rsplit("/", 1)[-1]
        if asset_id not in by_md5:
            with urllib.request.urlopen(urllib.request.Request(API.format(asset_id), headers=UA), timeout=60) as r:
                by_md5[asset_id] = {f["md5"]: f["url"] for f in _files(json.load(r), [])}
        md5 = hashlib.md5((library / a["path"]).read_bytes()).hexdigest()
        url = by_md5[asset_id].get(md5)
        if url is None:
            missing.append(a["path"])
            continue
        lock[a["path"]] = {"url": url, "sha256": a["sha256"]}
    if missing:
        raise SystemExit(f"no Poly Haven file matches {len(missing)} manifest entries: {missing}")
    manifest_sha = manifest_digest()
    LOCK.write_text(json.dumps({"schema": "valora.assets-lock/1", "manifest_sha256": manifest_sha, "files": lock},
                               indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {LOCK.relative_to(REPO)}: {len(lock)} files")


if __name__ == "__main__":
    main()
