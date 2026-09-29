"""Download the pinned library from Poly Haven into a directory, verifying every sha256 (CI image build).

    python3 worker/tools/fetch_assets.py OUT_DIR

Fails if the lock was made from a different manifest, or if any file's sha256 differs from the manifest.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "engine" / "assets" / "manifest.json"
LOCK = REPO / "worker" / "assets-lock.json"
UA = {"User-Agent": "valora3d-worker-build"}


def _fetch(out: Path, rel: str, entry: dict) -> None:
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(entry["url"], headers=UA), timeout=120) as r:
                data = r.read()
            break
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    got = hashlib.sha256(data).hexdigest()
    if got != entry["sha256"]:
        raise SystemExit(f"sha256 mismatch for {rel}: got {got}, manifest {entry['sha256']}")
    dest.write_bytes(data)


def main() -> None:
    out = Path(sys.argv[1])
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    assets = json.loads(MANIFEST.read_text(encoding="utf-8"))["assets"]
    if lock["manifest_sha256"] != hashlib.sha256(MANIFEST.read_bytes()).hexdigest():
        raise SystemExit("assets-lock.json is stale: run worker/tools/lock_assets.py")
    manifest = {a["path"]: a["sha256"] for a in assets.values()}
    if manifest != {p: e["sha256"] for p, e in lock["files"].items()}:
        raise SystemExit("assets-lock.json does not cover the manifest exactly")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda kv: _fetch(out, *kv), lock["files"].items()))
    print(f"fetched and verified {len(lock['files'])} files into {out}")


if __name__ == "__main__":
    main()
